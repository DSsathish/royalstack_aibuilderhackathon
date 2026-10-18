/** Red message under a form field, announced to screen readers; and the asterisk for mandatory fields. */
export default function FieldError({ msg }: { msg?: string }) {
  return msg ? <span role="alert" className="field-error">{msg}</span> : null;
}

export function Req() {
  return <span className="text-bad" aria-hidden> *</span>;
}
