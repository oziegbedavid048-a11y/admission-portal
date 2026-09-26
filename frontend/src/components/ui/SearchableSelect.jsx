import { useEffect, useMemo, useRef, useState } from 'react';
import Icon from '../../lib/icons';

/**
 * A single-choice select with a type-ahead filter, for lists too long to scan.
 * Arrow keys move through the filtered options, Enter picks and Escape closes,
 * so it works without a mouse.
 */
export default function SearchableSelect({
  options = [],
  value,
  onChange,
  placeholder = 'Select an option',
  id,
  labelledBy,
}) {
  const safeOptions = Array.isArray(options) ? options : [];
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const wrapRef = useRef(null);
  const searchRef = useRef(null);
  const listRef = useRef(null);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return safeOptions;
    return safeOptions.filter((option) =>
      String(option || '').toLowerCase().includes(needle)
    );
  }, [safeOptions, query]);

  useEffect(() => {
    if (!open) return undefined;
    const onDocumentClick = (event) => {
      if (!wrapRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocumentClick);
    return () => document.removeEventListener('mousedown', onDocumentClick);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setCursor(Math.max(0, safeOptions.indexOf(value)));
      window.setTimeout(() => searchRef.current?.focus(), 30);
    }
  }, [open, safeOptions, value]);

  useEffect(() => {
    if (!open || !listRef.current) return;
    const node = listRef.current.children[cursor];
    node?.scrollIntoView({ block: 'nearest' });
  }, [cursor, open]);

  const pick = (option) => {
    onChange(option);
    setOpen(false);
  };

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setCursor((c) => Math.min(filtered.length - 1, c + 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setCursor((c) => Math.max(0, c - 1));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (filtered[cursor]) pick(filtered[cursor]);
    } else if (event.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className="searchable-select-wrap" ref={wrapRef}>
      <div
        className={`searchable-input-box ${open ? 'active' : ''}`.trim()}
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-labelledby={labelledBy}
        tabIndex={0}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span style={value ? undefined : { color: 'var(--slate-400)' }}>
          {value || placeholder}
        </span>
        <Icon name="chevronDown" size={16} strokeWidth={2} />
      </div>

      <div className={`searchable-dropdown ${open ? 'show' : ''}`.trim()}>
        <input
          type="text"
          ref={searchRef}
          className="search-input-field"
          placeholder="Type to filter..."
          autoComplete="off"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setCursor(0);
          }}
          onKeyDown={onKeyDown}
        />
        <div role="listbox" ref={listRef}>
          {filtered.length === 0 ? (
            <div className="searchable-item" aria-disabled="true">
              Nothing matches that.
            </div>
          ) : (
            filtered.map((option, index) => (
              <div
                key={option}
                role="option"
                aria-selected={option === value}
                className={`searchable-item ${option === value ? 'selected' : ''} ${
                  index === cursor ? 'cursor' : ''
                }`.trim()}
                onMouseEnter={() => setCursor(index)}
                onClick={() => pick(option)}
              >
                {option}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
