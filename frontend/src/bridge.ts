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
        add_allocation?: (
          name: string,
          targetSeconds: number,
        ) => Promise<DashboardView>
        edit_allocation?: (
          allocationId: string,
          name: string,
          targetSeconds: number,
        ) => Promise<DashboardView>
        delete_allocation?: (allocationId: string) => Promise<DashboardView>
        set_name?: (name: string) => Promise<DashboardView>
        check_milestones?: (allocationId: string) => Promise<DashboardView>
        set_minimized?: (minimized: boolean) => Promise<void>
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

export const addAllocation = (
  name: string,
  targetSeconds: number,
): Promise<DashboardView> => api().add_allocation!(name, targetSeconds)
export const editAllocation = (
  id: string,
  name: string,
  targetSeconds: number,
): Promise<DashboardView> => api().edit_allocation!(id, name, targetSeconds)
export const deleteAllocation = (id: string): Promise<DashboardView> =>
  api().delete_allocation!(id)
export const setName = (name: string): Promise<DashboardView> =>
  api().set_name!(name)
export const checkMilestones = (id: string): Promise<DashboardView> =>
  api().check_milestones!(id)
export const setMinimized = (minimized: boolean): Promise<void> =>
  api().set_minimized!(minimized)
