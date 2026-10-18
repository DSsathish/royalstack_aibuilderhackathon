/** Small inline icon set (24px grid, 1.75 stroke). No emoji anywhere in the UI. */
const base = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
export const IconChat = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4z" /></svg>;
export const IconScan = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3M7 12h10" /></svg>;
export const IconCart = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M3 4h2l2.4 11.2a1 1 0 0 0 1 .8h8.9a1 1 0 0 0 1-.8L20 8H6.5" /><circle cx="9.5" cy="20" r="1.2" /><circle cx="16.5" cy="20" r="1.2" /></svg>;
export const IconMap = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2zM9 4v14M15 6v14" /></svg>;
export const IconMic = (p: { className?: string }) => <svg {...base} className={p.className}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>;
export const IconStop = (p: { className?: string }) => <svg {...base} className={p.className}><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" /></svg>;
export const IconCamera = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></svg>;
export const IconSend = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M4 12l16-8-6 16-2-7z" /></svg>;
export const IconSpeaker = (p: { className?: string; muted?: boolean }) => <svg {...base} className={p.className}><path d="M4 9v6h4l5 4V5L8 9z" />{p.muted ? <path d="M17 9l4 6M21 9l-4 6" /> : <path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11" />}</svg>;
export const IconCheck = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M5 12l5 5 9-10" /></svg>;
export const IconAlert = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M12 3l10 18H2zM12 10v5M12 18v.5" /></svg>;
export const IconPin = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M12 21s-6-6.2-6-11a6 6 0 0 1 12 0c0 4.8-6 11-6 11z" /><circle cx="12" cy="10" r="2.2" /></svg>;
export const IconPlus = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M12 5v14M5 12h14" /></svg>;
export const IconMinus = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M5 12h14" /></svg>;
export const IconClose = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M6 6l12 12M18 6L6 18" /></svg>;
export const IconBag = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M6 8h12l1 13H5zM9 8V6a3 3 0 0 1 6 0v2" /></svg>;
export const IconStore = (p: { className?: string }) => <svg {...base} className={p.className}><path d="M3 9l1.5-5h15L21 9M3 9v11h18V9M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0M9 20v-6h6v6" /></svg>;
export const IconSearch = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
);
