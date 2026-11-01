"use client";

import { useEffect, useRef, useState } from "react";
import {
  languages,
  getTranslation,
  normalizeTranslationText,
  type Language,
} from "../lib/localization";

const storageKey = "ordermesh-language";
const textValues = new WeakMap<Text, { source: string; rendered: string }>();
const attributeValues = new WeakMap<
  Element,
  Map<string, { source: string; rendered: string }>
>();

function isLanguage(value: string): value is Language {
  return languages.some((item) => item.code === value);
}

function isTranslatable(element: Element): boolean {
  return !element.closest(
    'script, style, noscript, code, pre, [contenteditable="true"], [data-i18n-ignore]',
  );
}

function isTextTranslatable(element: Element | null): boolean {
  if (!element) return false;
  return isTranslatable(element) && !element.closest("input, textarea, select, option");
}

function translateTextNode(node: Text, language: Language) {
  const current = node.nodeValue ?? "";
  const previous = textValues.get(node);
  const source =
    previous && current === previous.rendered ? previous.source : current;
  if (!source.trim()) return;

  const leading = source.match(/^\s*/)?.[0] ?? "";
  const trailing = source.match(/\s*$/)?.[0] ?? "";
  const normalized = normalizeTranslationText(source);
  const translated = getTranslation(language, normalized);
  const rendered = `${leading}${translated}${trailing}`;
  textValues.set(node, { source, rendered });
  if (rendered !== current) node.nodeValue = rendered;
}

function translateAttribute(element: Element, name: string, language: Language) {
  const current = element.getAttribute(name);
  if (current === null) return;
  let values = attributeValues.get(element);
  if (!values) {
    values = new Map();
    attributeValues.set(element, values);
  }
  const previous = values.get(name);
  const source = previous && current === previous.rendered ? previous.source : current;
  const translated = getTranslation(language, normalizeTranslationText(source));
  values.set(name, { source, rendered: translated });
  if (current !== translated) element.setAttribute(name, translated);
}

function translateElement(element: Element, language: Language) {
  if (!isTranslatable(element)) return;
  for (const name of ["aria-label", "title", "placeholder"]) {
    translateAttribute(element, name, language);
  }
  if (element.matches("input, textarea, select")) return;
  for (const child of element.childNodes) {
    if (child instanceof Text) {
      if (isTextTranslatable(element)) {
        translateTextNode(child, language);
      }
    } else if (child instanceof Element) {
      translateElement(child, language);
    }
  }
}

function applyTranslations(language: Language) {
  document.documentElement.lang = language;
  if (document.body) translateElement(document.body, language);
}

export default function SiteLanguage() {
  const [language, setLanguage] = useState<Language>("en");
  const languageRef = useRef<Language>("en");
  languageRef.current = language;

  useEffect(() => {
    const saved = window.localStorage.getItem(storageKey);
    if (saved && isLanguage(saved)) setLanguage(saved);
  }, []);

  useEffect(() => {
    applyTranslations(language);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData" && mutation.target instanceof Text) {
          const node = mutation.target;
          if (isTextTranslatable(node.parentElement ?? document.body)) {
            translateTextNode(node, languageRef.current);
          }
          continue;
        }
        if (mutation.type === "attributes" && mutation.target instanceof Element) {
          const element = mutation.target;
          if (isTranslatable(element) && mutation.attributeName) {
            translateAttribute(
              element,
              mutation.attributeName,
              languageRef.current,
            );
          }
          continue;
        }
        for (const node of mutation.addedNodes) {
          if (node instanceof Text) {
            const text = node;
            if (isTextTranslatable(text.parentElement ?? document.body)) {
              translateTextNode(text, languageRef.current);
            }
          } else if (node instanceof Element) {
            translateElement(node, languageRef.current);
          }
        }
      }
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["aria-label", "title", "placeholder"],
    });
    return () => observer.disconnect();
  }, [language]);

  function chooseLanguage(value: string) {
    if (!isLanguage(value)) {
      throw new Error(`Unsupported language selection: ${value}`);
    }
    window.localStorage.setItem(storageKey, value);
    setLanguage(value);
  }

  return (
    <label className="site-language">
      <span className="site-language-label">Language</span>
      <select
        aria-label="Select language"
        value={language}
        onChange={(event) => chooseLanguage(event.target.value)}
      >
        {languages.map((item) => (
          <option key={item.code} value={item.code}>
            {item.name}
          </option>
        ))}
      </select>
    </label>
  );
}
