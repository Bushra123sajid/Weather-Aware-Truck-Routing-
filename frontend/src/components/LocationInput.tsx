import { useId, useState } from 'react';
import { MapPin } from 'lucide-react';
import type { Place } from '../api/types';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useGeocode } from '../hooks/useApi';

export interface LocationValue {
  text: string;
  place: Place | null;
}

interface Props {
  label: string;
  value: LocationValue;
  onChange: (v: LocationValue) => void;
  error?: string | null;
  placeholder?: string;
  disabled?: boolean;
}

/** Combobox with geocoding suggestions; queries are debounced to respect Nominatim's rate limit. */
export function LocationInput({ label, value, onChange, error, placeholder, disabled }: Props) {
  const id = useId();
  const listId = `${id}-list`;
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const debounced = useDebouncedValue(value.place ? '' : value.text, 400);
  const { data: results = [], isFetching, isError } = useGeocode(debounced);
  const showList = open && !value.place && value.text.trim().length >= 3;

  const choose = (place: Place) => {
    onChange({ text: place.label, place });
    setOpen(false);
    setActive(-1);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showList || results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => (a + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => (a <= 0 ? results.length - 1 : a - 1));
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault();
      choose(results[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className="field location-input">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-err` : undefined}
        placeholder={placeholder}
        disabled={disabled}
        value={value.text}
        onChange={(e) => {
          onChange({ text: e.target.value, place: null });
          setOpen(true);
          setActive(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
      />
      {value.place && (
        <span className="location-input__ok" aria-label="Location selected">
          <MapPin size={16} aria-hidden="true" />
        </span>
      )}
      {showList && (
        <ul id={listId} role="listbox" className="suggestions">
          {isFetching && results.length === 0 && <li className="suggestions__info">Searching</li>}
          {isError && (
            <li className="suggestions__info">Search is unavailable. Try again in a moment.</li>
          )}
          {!isFetching && !isError && results.length === 0 && debounced.length >= 3 && (
            <li className="suggestions__info">No matches</li>
          )}
          {results.map((p, i) => (
            <li
              key={`${p.lat},${p.lng},${i}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'active' : undefined}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(p);
              }}
            >
              {p.label}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p id={`${id}-err`} className="field__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
