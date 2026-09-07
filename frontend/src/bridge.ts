import type { DashboardView } from './types'

declare global {
  interface Window {
    // Both levels are optional: pywebview creates `window.pywebview` as soon
    // as its own api.js runs, but attaches the api methods later.
    pywebview?: {
      api?: {
        ui_ready?: () => Promise<DashboardView>
        resume?: () => Promise<DashboardView>
        activate?: (allocationId: string) => Promise<DashboardView>
        toggle_break?: () => Promise<DashboardView>
        complete_day?: () => Promise<DashboardView>
      }
    }
  }
}

function api() {
  const bridge = window.pywebview?.api
  if (!bridge) throw new Error('pywebview bridge is not available')
  return bridge
}

export const uiReady = (): Promise<DashboardView> => api().ui_ready!()
export const resume = (): Promise<DashboardView> => api().resume!()
export const activate = (id: string): Promise<DashboardView> => api().activate!(id)
export const toggleBreak = (): Promise<DashboardView> => api().toggle_break!()
export const completeDay = (): Promise<DashboardView> => api().complete_day!()
