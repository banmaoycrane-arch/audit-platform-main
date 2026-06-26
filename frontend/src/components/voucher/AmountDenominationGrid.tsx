import { Input, InputNumber } from 'antd'
import { useEffect, useRef } from 'react'
import {
  DENOM_CELL_COUNT,
  DENOM_LABELS,
  amountToDenomCells,
  denomCellsToAmount,
  roundAmount,
} from './voucherAmountUtils'
import './TraditionalVoucherForm.css'

interface AmountDenominationGridProps {
  value: number
  onChange?: (amount: number) => void
  readOnly?: boolean
  quickEntry?: boolean
  inputNamePrefix?: string
}

export function AmountDenominationGrid({
  value,
  onChange,
  readOnly = false,
  quickEntry = false,
  inputNamePrefix = 'amount',
}: AmountDenominationGridProps) {
  const inputRefs = useRef<Array<HTMLInputElement | null>>([])

  useEffect(() => {
    inputRefs.current = inputRefs.current.slice(0, DENOM_CELL_COUNT)
  }, [])

  const cells = amountToDenomCells(value)

  const emitChange = (nextCells: string[]) => {
    if (!onChange) return
    onChange(denomCellsToAmount(nextCells))
  }

  const focusCell = (index: number) => {
    const target = inputRefs.current[index]
    if (target) {
      target.focus()
      target.select()
    }
  }

  const handleCellChange = (index: number, raw: string) => {
    if (readOnly || !onChange) return
    const digit = raw.replace(/\D/g, '').slice(-1)
    const nextCells = [...cells]
    nextCells[index] = digit
    emitChange(nextCells)
    if (digit && index < DENOM_CELL_COUNT - 1) {
      focusCell(index + 1)
    }
  }

  const handleCellKeyDown = (index: number, key: string) => {
    if (key === 'Backspace' && !cells[index] && index > 0) {
      focusCell(index - 1)
    }
    if (key === 'ArrowLeft' && index > 0) {
      focusCell(index - 1)
    }
    if (key === 'ArrowRight' && index < DENOM_CELL_COUNT - 1) {
      focusCell(index + 1)
    }
  }

  if (quickEntry && !readOnly) {
    return (
      <div className="voucher-amount-quick">
        <InputNumber
          min={0}
          precision={2}
          value={value || undefined}
          placeholder="0.00"
          onChange={(next) => onChange?.(roundAmount(Number(next || 0)))}
          className="voucher-amount-quick-input"
        />
      </div>
    )
  }

  return (
    <div className={`voucher-amount-grid${readOnly ? ' is-readonly' : ''}`}>
      {DENOM_LABELS.map((label, index) => (
        <div key={`${inputNamePrefix}-${label}-${index}`} className="voucher-amount-cell">
          {readOnly ? (
            <span className="voucher-amount-digit">{cells[index] || ''}</span>
          ) : (
            <input
              ref={(node) => { inputRefs.current[index] = node }}
              className="voucher-amount-digit-input"
              value={cells[index] || ''}
              maxLength={1}
              inputMode="numeric"
              aria-label={`${label}位`}
              onChange={(event) => handleCellChange(index, event.target.value)}
              onKeyDown={(event) => handleCellKeyDown(index, event.key)}
            />
          )}
        </div>
      ))}
    </div>
  )
}
