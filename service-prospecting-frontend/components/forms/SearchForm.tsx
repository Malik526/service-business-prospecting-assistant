/** Search form for ZIP, radius, and category input.
 *  Props: onSearch handles submitted values; loading disables controls during API calls.
 */

import { Search } from "lucide-react";
import { FormEvent, useState } from "react";

import { categoryOptions, defaultSearchValues } from "../../lib/content";
import styles from "../../styles/prospecting.module.css";

interface SearchFormProps {
  onSearch: (zipCode: string, radius: number, categories: string) => void;
  loading: boolean;
}

/** Renders the prospect search controls and validates required ZIP input. */
export function SearchForm({ onSearch, loading }: SearchFormProps): JSX.Element {
  const [zipCode, setZipCode] = useState(defaultSearchValues.zipCode);
  const [radius, setRadius] = useState(defaultSearchValues.radius);
  const [categoryMode, setCategoryMode] = useState<"custom" | "preset">("custom");
  const [customCategories, setCustomCategories] = useState(defaultSearchValues.categories);
  const [selectedPreset, setSelectedPreset] = useState(categoryOptions[0].value);

  /** Sends normalized search values to the parent page. */
  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const categories = categoryMode === "preset" ? selectedPreset : customCategories;
    onSearch(zipCode.trim(), radius, categories.trim());
  }

  return (
    <form className={styles.searchForm} onSubmit={handleSubmit}>
      <div className={styles.formGrid}>
        <label className={styles.inputGroup} htmlFor="zip-code">
          <span>ZIP code</span>
          <input
            id="zip-code"
            type="text"
            inputMode="numeric"
            value={zipCode}
            onChange={(event) => setZipCode(event.target.value)}
            placeholder="11385"
            maxLength={10}
            required
          />
        </label>

        <label className={styles.inputGroup} htmlFor="radius">
          <span>Radius: {radius} mi</span>
          <input
            id="radius"
            type="range"
            min="1"
            max="100"
            value={radius}
            onChange={(event) => setRadius(Number(event.target.value))}
          />
        </label>

        <label className={styles.inputGroup} htmlFor="category-mode">
          <span>Category mode</span>
          <select
            id="category-mode"
            value={categoryMode}
            onChange={(event) => setCategoryMode(event.target.value as "custom" | "preset")}
          >
            <option value="custom">Custom list</option>
            <option value="preset">Single preset</option>
          </select>
        </label>

        {categoryMode === "preset" ? (
          <label className={styles.inputGroup} htmlFor="preset-category">
            <span>Preset category</span>
            <select
              id="preset-category"
              value={selectedPreset}
              onChange={(event) => setSelectedPreset(event.target.value)}
            >
              {categoryOptions.map((category) => (
                <option key={category.value} value={category.value}>
                  {category.label}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className={styles.inputGroup} htmlFor="custom-categories">
            <span>Categories</span>
            <input
              id="custom-categories"
              type="text"
              value={customCategories}
              onChange={(event) => setCustomCategories(event.target.value)}
              placeholder="electrician, plumber, hvac"
            />
          </label>
        )}
      </div>

      <button className={styles.searchButton} type="submit" disabled={loading}>
        <Search aria-hidden="true" size={18} />
        <span>{loading ? "Searching" : "Search prospects"}</span>
      </button>
    </form>
  );
}

