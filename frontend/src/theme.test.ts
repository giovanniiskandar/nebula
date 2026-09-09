import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The Break theme is a block of token overrides, so it only reaches
 * declarations that read a token. A colour written into a component is
 * invisible to it, and the card renders green with purple-grey parts.
 */
const COMPONENTS = fileURLToPath(new URL('./components', import.meta.url))

describe('the palette', () => {
  it('lives in index.css, not in component stylesheets', () => {
    const offenders = readdirSync(COMPONENTS)
      .filter((name) => name.endsWith('.css'))
      .flatMap((name) => {
        const hexes = readFileSync(`${COMPONENTS}/${name}`, 'utf8').match(
          /#[0-9a-fA-F]{3,8}\b/g,
        )
        return hexes === null ? [] : [`${name}: ${hexes.join(', ')}`]
      })

    expect(offenders).toEqual([])
  })
})
