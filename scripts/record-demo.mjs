#!/usr/bin/env node
/**
 * Records `assets/demo.gif` -- the twelve seconds of the app in the README.
 *
 * Drives `frontend/demo.html` (a dev-only Vite entry that feeds the real
 * dashboard an in-memory day) in headless Chrome, then encodes the capture with
 * ffmpeg. Playwright is not a dependency of this project: it is installed on
 * first run into `scripts/.demo-tools/`, which is gitignored, and it drives the
 * Chrome already on the machine rather than downloading a browser of its own.
 *
 *   node scripts/record-demo.mjs [--out assets/demo.gif] [--fps 15]
 *                                [--headed] [--keep-video]
 */

import { spawn } from 'node:child_process'
import { mkdtemp, mkdir, rm, access } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const TOOLS = join(ROOT, 'scripts', '.demo-tools')
const DEV_URL = 'http://localhost:5173'
const DEMO_URL = `${DEV_URL}/demo.html`

/** The native window's size (CARD + SHADOW_PADDING * 2, see src/nebula/app.py). */
const WIDTH = 384
const HEIGHT = 684
/**
 * How much the demo page is zoomed for the recording.
 *
 * Playwright's video is the viewport's own size. Asking `recordVideo.size` for
 * a larger frame does not scale the page up -- it fits the page in at its
 * natural size and pads the rest of the frame grey, which is how the first two
 * recordings ended up three-quarters dead space. So the viewport is enlarged
 * and the page zoomed to match: the card is painted at this scale, not
 * resampled to it. 1.5 puts the GIF at 576x1026, which is exactly 2x the 288
 * the README displays it at -- crisp on a retina screen, with no pixels paid
 * for that no screen can show.
 */
const OUTPUT_SCALE = 1.5

const args = process.argv.slice(2)
const flag = (name, fallback) => {
  const index = args.indexOf(`--${name}`)
  return index === -1 ? fallback : args[index + 1]
}
const out = resolve(ROOT, flag('out', 'assets/demo.gif'))
const fps = Number(flag('fps', '15'))
const headed = args.includes('--headed')
const keepVideo = args.includes('--keep-video')

const run = (command, commandArgs, options = {}) =>
  new Promise((resolvePromise, reject) => {
    const child = spawn(command, commandArgs, { stdio: 'inherit', ...options })
    child.on('error', reject)
    child.on('exit', (code) =>
      code === 0
        ? resolvePromise()
        : reject(new Error(`${command} exited with ${code}`)),
    )
  })

const capture = (command, commandArgs) =>
  new Promise((resolvePromise, reject) => {
    const child = spawn(command, commandArgs)
    let stdout = ''
    child.stdout.on('data', (chunk) => (stdout += chunk))
    child.on('error', reject)
    child.on('exit', (code) =>
      code === 0 ? resolvePromise(stdout.trim()) : reject(new Error(`${command} failed`)),
    )
  })

const captureBytes = (command, commandArgs) =>
  new Promise((resolvePromise, reject) => {
    const child = spawn(command, commandArgs)
    const chunks = []
    child.stdout.on('data', (chunk) => chunks.push(chunk))
    child.on('error', reject)
    child.on('exit', (code) =>
      code === 0
        ? resolvePromise(Buffer.concat(chunks))
        : reject(new Error(`${command} failed`)),
    )
  })

const exists = (path) =>
  access(path).then(
    () => true,
    () => false,
  )

async function serverIsUp() {
  try {
    const response = await fetch(DEMO_URL, { signal: AbortSignal.timeout(1000) })
    return response.ok
  } catch {
    return false
  }
}

/** The dev server, started only if one is not already running. */
async function startDevServer() {
  if (await serverIsUp()) return null

  console.log('· starting the Vite dev server')
  const child = spawn('pnpm', ['exec', 'vite'], {
    cwd: join(ROOT, 'frontend'),
    stdio: 'ignore',
    // Its own group, so killing it takes the whole pnpm/vite tree down.
    detached: true,
  })

  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise((r) => setTimeout(r, 500))
    if (await serverIsUp()) return child
  }
  throw new Error('the dev server never came up on port 5173')
}

async function loadPlaywright() {
  const entry = join(TOOLS, 'node_modules', 'playwright', 'index.js')
  if (!(await exists(entry))) {
    console.log('· installing Playwright into scripts/.demo-tools (first run only)')
    await mkdir(TOOLS, { recursive: true })
    await run('npm', ['install', '--silent', '--no-save', '--prefix', TOOLS, 'playwright'])
  }
  // A CommonJS package: the browser types hang off `default` under `import()`.
  const module = await import(pathToFileURL(entry).href)
  return module.chromium === undefined ? module.default : module
}

async function record(playwright, videoDir) {
  // Chrome is already on the machine; the bundled Chromium is a 100MB+ download
  // for a browser that would render this identically.
  let browser
  try {
    browser = await playwright.chromium.launch({ channel: 'chrome', headless: !headed })
  } catch {
    console.log('· no system Chrome; falling back to Playwright Chromium')
    await run('node', [join(TOOLS, 'node_modules', 'playwright', 'cli.js'), 'install', 'chromium'])
    browser = await playwright.chromium.launch({ headless: !headed })
  }

  const frame = { width: WIDTH * OUTPUT_SCALE, height: HEIGHT * OUTPUT_SCALE }
  const context = await browser.newContext({
    // Viewport, zoom and video all at the same size: nothing left for
    // Playwright to letterbox.
    viewport: frame,
    deviceScaleFactor: 1,
    recordVideo: { dir: videoDir, size: frame },
  })

  const page = await context.newPage()
  page.on('console', (message) => {
    if (message.type() === 'error') console.error(`  page error: ${message.text()}`)
  })
  page.on('pageerror', (error) => console.error(`  page error: ${error.message}`))

  await page.goto(`${DEMO_URL}?scale=${OUTPUT_SCALE}`, { waitUntil: 'load' })
  console.log('· playing the beat sheet')
  await page.waitForFunction(
    () => document.documentElement.dataset.demoDone === 'true',
    undefined,
    { timeout: 60_000 },
  )

  // The beat sheet's own length, published by src/demo/main.tsx: a constant
  // repeated here would silently encode the wrong window once the beats change.
  const demoSeconds = await page.evaluate(
    () => Number(document.documentElement.dataset.demoMs) / 1000,
  )

  const video = page.video()
  // The file is only finalised on close, and only then does it have a path.
  await context.close()
  const source = await video.path()
  await browser.close()

  if (!Number.isFinite(demoSeconds) || demoSeconds <= 0) {
    throw new Error('the demo page did not publish its duration')
  }
  return { source, demoSeconds }
}

async function encode(source, videoDir, demoSeconds) {
  // Recording starts when the context opens, so the capture is the demo plus
  // however long the page took to paint: take the twelve seconds at the end.
  // The floor also steps over the capture's first frame, which Chrome emits at
  // its own size before the viewport settles.
  const duration = Number(
    await capture('ffprobe', [
      '-v', 'error',
      '-show_entries', 'format=duration',
      '-of', 'csv=p=0',
      source,
    ]),
  )
  const start = Math.max(0.08, duration - demoSeconds)
  console.log(
    `· encoding ${demoSeconds}s at ${fps}fps from a ${duration.toFixed(1)}s capture`,
  )

  // Two passes over an explicit WIDTHxHEIGHT, not one `split` graph: that first
  // odd-sized frame reaches `palettegen` unscaled and the palette it builds
  // paints the opening second white.
  const scaled =
    `fps=${fps},scale=${WIDTH * OUTPUT_SCALE}:${HEIGHT * OUTPUT_SCALE}:flags=lanczos`
  const palette = join(videoDir, 'palette.png')
  const trim = ['-ss', String(start), '-i', source, '-t', String(demoSeconds)]

  await run('ffmpeg', [
    '-v', 'error', '-y',
    ...trim,
    '-vf', `${scaled},palettegen=max_colors=128:stats_mode=diff`,
    palette,
  ])

  await mkdir(dirname(out), { recursive: true })
  await run('ffmpeg', [
    '-v', 'error', '-y',
    ...trim,
    '-i', palette,
    '-filter_complex',
    // No dithering: the card is flat and nearly monochrome, so bayer was
    // indistinguishable at 1:1 and cost a megabyte in noise the GIF then had
    // to encode.
    `[0:v]${scaled}[v];[v][1:v]paletteuse=dither=none:diff_mode=rectangle`,
    '-loop', '0',
    out,
  ])
}

/**
 * Fail on a padded frame rather than shipping one.
 *
 * A letterboxed capture is not obvious in a contact sheet -- grey margins read
 * as the sheet's own padding -- and it reached the README twice before anyone
 * noticed. The app's ground is #0b0910, so a corner of the finished GIF is
 * near-black; Playwright's padding is mid grey.
 */
async function assertNotPadded() {
  const corner = await captureBytes('ffmpeg', [
    '-v', 'error',
    '-i', out,
    '-vf', 'crop=64:64:iw-64:ih-64,scale=1:1',
    '-frames:v', '1',
    '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-',
  ])
  const luma = (corner[0] + corner[1] + corner[2]) / 3
  if (luma > 60) {
    throw new Error(
      `the capture is padded: the GIF's bottom-right corner reads ${Math.round(luma)}/255, ` +
        'not the app\'s near-black ground. The viewport, the page zoom and ' +
        'recordVideo.size must all be the same size.',
    )
  }
}

const videoDir = await mkdtemp(join(tmpdir(), 'nebula-demo-'))
let server = null
try {
  server = await startDevServer()
  const playwright = await loadPlaywright()
  const { source, demoSeconds } = await record(playwright, videoDir)
  await encode(source, videoDir, demoSeconds)
  await assertNotPadded()
  console.log(`· wrote ${out}`)
} finally {
  if (server !== null) process.kill(-server.pid)
  if (keepVideo) console.log(`· capture kept in ${videoDir}`)
  else await rm(videoDir, { recursive: true, force: true })
}
