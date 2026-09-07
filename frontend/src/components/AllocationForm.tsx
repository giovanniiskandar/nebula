import { useState } from 'react'
import { formatDuration } from '../format'
import { PRESETS, clampMinutes, joinTarget, plannedAfter, splitTarget } from '../targets'
import type { AllocationView, DashboardView } from '../types'
import styles from './AllocationForm.module.css'

interface Props {
  view: DashboardView
  /** The allocation being edited, or null when adding. */
  editing: AllocationView | null
  onCancel: () => void
  onSave: (name: string, targetSeconds: number) => void
}

export function AllocationForm({ view, editing, onCancel, onSave }: Props) {
  const [name, setName] = useState(editing?.name ?? '')
  const [parts, setParts] = useState(() =>
    splitTarget(editing?.dailyTargetSeconds ?? 0),
  )

  const targetSeconds = joinTarget(parts.hours, parts.minutes)
  // An allocation's name is required; the user's name in Settings is not.
  const canSave = name.trim().length > 0 && targetSeconds > 0

  const plannedNow = view.totalTargetSeconds
  const plannedNext = plannedAfter(view, editing?.id ?? null, targetSeconds)

  return (
    <div className={styles.form} data-form>
      <header className={styles.header}>
        <span className={styles.title}>
          {editing === null ? 'NEW ALLOCATION' : editing.name.toUpperCase()}
        </span>
      </header>

      <label className={styles.field}>
        <span className={styles.label}>NAME</span>
        <input
          type="text"
          data-form-name
          className={styles.input}
          value={name}
          placeholder="Work"
          onChange={(event) => setName(event.target.value)}
        />
      </label>

      <div className={styles.field}>
        <span className={styles.label}>DAILY TARGET</span>
        <div className={styles.chips}>
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              data-preset={preset.label}
              className={`${styles.chip} ${
                targetSeconds === preset.seconds ? styles.chipOn : ''
              }`}
              onClick={() => setParts(splitTarget(preset.seconds))}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className={styles.duration}>
          <input
            type="number"
            min={0}
            data-form-hours
            className={styles.number}
            value={parts.hours}
            onChange={(event) =>
              setParts({ ...parts, hours: Number(event.target.value) })
            }
            onBlur={() => setParts(clampMinutes(parts))}
          />
          <span className={styles.unit}>hh</span>
          <input
            type="number"
            min={0}
            data-form-minutes
            className={styles.number}
            value={parts.minutes}
            onChange={(event) =>
              setParts({ ...parts, minutes: Number(event.target.value) })
            }
            onBlur={() => setParts(clampMinutes(parts))}
          />
          <span className={styles.unit}>mm</span>
        </div>
      </div>

      <div className={styles.planned}>
        <span className={styles.label}>DAY AFTER THIS</span>
        <span className={styles.plannedValue}>
          {formatDuration(plannedNow)} planned → {formatDuration(plannedNext)} planned
        </span>
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.cancel}
          data-form-cancel
          onClick={onCancel}
        >
          CANCEL
        </button>
        <button
          type="button"
          data-form-save
          className={styles.save}
          disabled={!canSave}
          onClick={() => onSave(name.trim(), targetSeconds)}
        >
          SAVE
        </button>
      </div>
    </div>
  )
}
