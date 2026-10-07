const WORD_CHARACTER = /[\p{L}\p{N}]/u;

/**
 * Lowercases text and collapses every run of non-word characters (whitespace, line breaks,
 * markdown syntax) to one space, keeping each output character's index in the original text.
 */
function normalize(text: string): { value: string; offsets: number[] } {
  let value = "";
  const offsets: number[] = [];
  for (let index = 0; index < text.length; index++) {
    const character = text[index];
    if (WORD_CHARACTER.test(character)) {
      for (const lowered of character.toLowerCase()) {
        value += lowered;
        offsets.push(index);
      }
    } else if (value && !value.endsWith(" ")) {
      value += " ";
      offsets.push(index);
    }
  }
  if (value.endsWith(" ")) {
    value = value.slice(0, -1);
    offsets.pop();
  }
  return { value, offsets };
}

/** Where the excerpt appears in the text, as [start, end) offsets into the original text. */
export function findExcerpt(
  text: string,
  excerpt: string | null | undefined,
): { start: number; end: number } | null {
  const needle = normalize(excerpt ?? "").value;
  if (!needle) return null;
  const haystack = normalize(text);
  const position = haystack.value.indexOf(needle);
  if (position === -1) return null;
  return {
    start: haystack.offsets[position],
    end: haystack.offsets[position + needle.length - 1] + 1,
  };
}
