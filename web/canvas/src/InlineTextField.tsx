import { useEffect, useLayoutEffect, useRef, useState } from 'react';

interface InlineTextFieldProps {
  value: string;
  label: string;
  className?: string;
  placeholder?: string;
  onChange: (value: string) => void;
  onComposingChange: (composing: boolean) => void;
}

/** Keep IME drafts local, then publish the exact completed text to the canvas. */
export function InlineTextField({ value, label, className = '', placeholder, onChange, onComposingChange }: InlineTextFieldProps) {
  const [draft, setDraft] = useState(value);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const composing = useRef(false);
  const currentDraft = useRef(value);
  const committed = useRef(value);
  const actions = useRef({ onChange, onComposingChange });
  actions.current = { onChange, onComposingChange };

  useEffect(() => {
    if (composing.current) return;
    currentDraft.current = value;
    committed.current = value;
    setDraft(value);
  }, [value]);

  useLayoutEffect(() => {
    const field = textarea.current;
    if (!field) return;
    field.style.height = 'auto';
    field.style.height = `${field.scrollHeight + field.offsetHeight - field.clientHeight}px`;
  }, [draft]);

  useEffect(() => () => {
    if (!composing.current) return;
    if (currentDraft.current !== committed.current) actions.current.onChange(currentDraft.current);
    composing.current = false;
    actions.current.onComposingChange(false);
  }, []);

  const commit = (next: string) => {
    if (next === committed.current) return;
    committed.current = next;
    actions.current.onChange(next);
  };
  const finishComposition = (next: string) => {
    currentDraft.current = next;
    setDraft(next);
    commit(next);
    if (composing.current) {
      composing.current = false;
      actions.current.onComposingChange(false);
    }
  };

  return <textarea
    ref={textarea}
    aria-label={label}
    className={`inline-text-field nodrag nowheel ${className}`}
    value={draft}
    rows={1}
    placeholder={placeholder}
    onPointerDown={(event) => event.stopPropagation()}
    onKeyDown={(event) => event.stopPropagation()}
    onClick={(event) => event.stopPropagation()}
    onChange={(event) => {
      const next = event.currentTarget.value;
      currentDraft.current = next;
      setDraft(next);
      if (!composing.current) commit(next);
    }}
    onCompositionStart={() => {
      if (composing.current) return;
      composing.current = true;
      actions.current.onComposingChange(true);
    }}
    onCompositionEnd={(event) => finishComposition(event.currentTarget.value)}
    onBlur={(event) => finishComposition(event.currentTarget.value)}
  />;
}
