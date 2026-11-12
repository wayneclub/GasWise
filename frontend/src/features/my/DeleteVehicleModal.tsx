import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'

interface DeleteVehicleModalProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
}

export function DeleteVehicleModal({ open, onClose, onConfirm }: DeleteVehicleModalProps) {
  const { t } = useI18n()

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
    >
      <div className="w-full max-w-sm rounded-box border border-line bg-surface p-5 shadow-2xl flex flex-col gap-4">
        <h3 className="text-sm font-bold text-ink">{t('garage.remove')}</h3>
        <p className="text-xs text-muted leading-relaxed">{t('garage.confirmRemove')}</p>
        <div className="flex justify-end gap-2 pt-2 border-t border-line">
          <Button
            variant="secondary"
            onClick={onClose}
            className="min-h-9 text-xs"
          >
            {t('garage.cancel')}
          </Button>
          <Button
            variant="primary"
            onClick={onConfirm}
            className="min-h-9 text-xs bg-rose-600 hover:bg-rose-700 text-white"
          >
            {t('garage.remove')}
          </Button>
        </div>
      </div>
    </div>
  )
}
