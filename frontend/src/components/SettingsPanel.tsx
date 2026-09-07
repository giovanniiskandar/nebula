import { formatDuration } from '../format'
import type { AllocationView, DashboardView } from '../types'
import styles from './SettingsPanel.module.css'

interface Props {
  view: DashboardView
  onClose: () => void
  onAdd: () => void
  onEdit: (allocation: AllocationView) => void
  onDelete: (id: string) => void
  onNameChange: (name: string) => void
}

export function SettingsPanel({
  view,
  onClose,
  onAdd,
  onEdit,
  onDelete,
  onNameChange,
}: Props) {
  return (
    <div className={styles.panel} data-settings>
      <header className={styles.header}>
        <span className={styles.title}>TIME ALLOCATIONS</span>
        <span className={styles.total}>
          {formatDuration(view.totalTargetSeconds)} / day
        </span>
      </header>

      <div className={styles.list}>
        {view.allocations.map((allocation) => (
          <div key={allocation.id} className={styles.row} data-settings-row>
            <div className={styles.info}>
              <span className={styles.name} data-settings-name>
                {allocation.name}
              </span>
              <span className={styles.meta}>
                {formatDuration(allocation.dailyTargetSeconds)} / day ·{' '}
                {allocation.daysTracked} days tracked
              </span>
            </div>
            <button
              type="button"
              className={styles.action}
              onClick={() => onEdit(allocation)}
            >
              Edit
            </button>
            {/* No confirmation step and no archived view (PRD §12). */}
            <button
              type="button"
              className={styles.action}
              data-delete
              onClick={() => onDelete(allocation.id)}
            >
              Delete
            </button>
          </div>
        ))}
      </div>

      <button type="button" className={styles.add} data-add onClick={onAdd}>
        + ADD ALLOCATION
      </button>

      <label className={styles.nameField}>
        <span className={styles.title}>YOUR NAME</span>
        {/* Optional, may be blank, and saves on blur -- there is nothing to
            validate, so a Save button would be ceremony. */}
        <input
          type="text"
          data-user-name
          className={styles.input}
          defaultValue={view.userName ?? ''}
          placeholder="optional"
          onBlur={(event) => onNameChange(event.target.value)}
        />
      </label>

      <button
        type="button"
        className={styles.close}
        data-settings-close
        onClick={onClose}
      >
        &times;
      </button>
    </div>
  )
}
