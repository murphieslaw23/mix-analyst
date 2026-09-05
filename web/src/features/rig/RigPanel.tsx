import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/Button";

interface RigPanelProps {
  mixId: string;
  onClose: () => void;
}

function reducedMotionPreferred() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/**
 * An optional, deliberately non-strobing listening reference. It is lazy so
 * neither visual presentation nor hardware APIs can block result recovery.
 */
export default function RigPanel({ mixId, onClose }: RigPanelProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [cabinet, setCabinet] = useState("press-plate");
  const [reducedMotion] = useState(reducedMotionPreferred);

  useEffect(() => {
    const first = dialogRef.current?.querySelector<HTMLElement>("button, [href], select");
    first?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key === "Tab" && dialogRef.current) {
        const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), [href], select:not([disabled])")];
        if (!focusable.length) return;
        const firstItem = focusable[0];
        const lastItem = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === firstItem) { event.preventDefault(); lastItem.focus(); }
        else if (!event.shiftKey && document.activeElement === lastItem) { event.preventDefault(); firstItem.focus(); }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="rig-backdrop" data-testid="rig-panel" data-motion={reducedMotion ? "reduced" : "standard"} role="presentation">
      <div aria-describedby="rig-description" aria-labelledby="rig-title" aria-modal="true" className="rig-dialog" ref={dialogRef} role="dialog">
        <div className="rig-dialog__heading"><div><p className="eyebrow">Optional listening reference</p><h2 id="rig-title">Listening rig</h2></div><Button onClick={onClose} tone="quiet">Close rig</Button></div>
        <p id="rig-description">A visual reference for mix {mixId}. It does not change, upload, or control your audio.</p>
        <label className="rig-dialog__field" htmlFor="rig-cabinet"><span>Cabinet arrangement</span><select id="rig-cabinet" onChange={(event) => setCabinet(event.target.value)} value={cabinet}><option value="press-plate">Press Plate stack</option><option value="wall">Wall of sound</option><option value="twin">Twin stack</option></select></label>
        <div aria-label={`${cabinet} speaker reference`} className="rig-speaker-stack" role="img"><span /><span /><span /><span /></div>
        <p className="rig-dialog__hint">The Rig remains still when your device requests reduced motion. Use Escape or Close rig to return to playback.</p>
      </div>
    </div>
  );
}
