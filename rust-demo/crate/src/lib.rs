//! shortlinks: a tiny in-memory short-link store.
//!
//! Deliberately zero-dependency so the rust-demo harness keeps builds small;
//! it is still a realistic crate: base62 codes, collision-free insertion,
//! hit counters and aggregate stats.

pub mod code;
pub mod stats;

use std::collections::HashMap;

pub use code::Code;

/// Upper bound on stored links; inserting past this fails fast instead of
/// letting the map grow unbounded. Kept as a const so harnesses have a
/// well-defined one-line "small edit" knob.
pub const MAX_LINKS: usize = 10_000;

/// An in-memory short-link store: code -> (url, hits).
#[derive(Debug, Default)]
pub struct ShortLinks {
    by_code: HashMap<String, Entry>,
    counter: u64,
}

#[derive(Debug)]
struct Entry {
    url: String,
    hits: u64,
}

impl ShortLinks {
    /// Creates an empty store.
    pub fn new() -> ShortLinks {
        ShortLinks::default()
    }

    /// Inserts `url` and returns the freshly allocated [`Code`] for it.
    ///
    /// URLs are stored verbatim; codes are dense counters, so insertions are
    /// collision-free by construction. Returns `None` from [`Self::insert_opt`]
    /// once [`MAX_LINKS`] is reached.
    pub fn insert(&mut self, url: &str) -> Code {
        self.insert_opt(url).expect("MAX_LINKS exceeded")
    }

    /// Like [`Self::insert`] but returns `None` instead of panicking when the
    /// store is full.
    pub fn insert_opt(&mut self, url: &str) -> Option<Code> {
        if self.by_code.len() >= MAX_LINKS {
            return None;
        }
        self.counter += 1;
        let code = Code::new(self.counter);
        self.by_code.insert(
            code.to_base62(),
            Entry {
                url: url.to_string(),
                hits: 0,
            },
        );
        Some(code)
    }

    /// Resolves a code string (any case, surrounding whitespace tolerated)
    /// to the stored URL, or `None` if unknown.
    pub fn resolve(&self, code: &str) -> Option<&str> {
        let key = normalize_code(code);
        self.by_code.get(&key).map(|e| e.url.as_str())
    }

    /// Hit counter for a code string, or `None` if unknown.
    pub fn hits(&self, code: &str) -> Option<u64> {
        let key = normalize_code(code);
        self.by_code.get(&key).map(|e| e.hits)
    }

    /// Number of stored links.
    pub fn len(&self) -> usize {
        self.by_code.len()
    }

    /// True when no links are stored.
    pub fn is_empty(&self) -> bool {
        self.by_code.is_empty()
    }

    /// Sum of all hit counters.
    pub fn total_hits(&self) -> u64 {
        self.by_code.values().map(|e| e.hits).sum()
    }

    /// Iterator over the canonical (base62) code strings currently stored.
    pub fn codes(&self) -> impl Iterator<Item = &String> {
        self.by_code.keys()
    }

    /// URL for an exact canonical code string, without normalization.
    /// (Distinct from [`Self::resolve`], which normalizes user input.)
    pub fn url_of(&self, code: &str) -> Option<&str> {
        self.by_code.get(code).map(|e| e.url.as_str())
    }
}

/// Codes are matched case-insensitively: lowercase, trimmed.
fn normalize_code(code: &str) -> String {
    code.trim().to_ascii_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn insert_and_resolve() {
        let mut links = ShortLinks::new();
        let c1 = links.insert("https://example.com/a");
        let c2 = links.insert("https://example.com/b");
        assert_ne!(c1, c2);
        assert_eq!(links.resolve(&c1.to_base62()), Some("https://example.com/a"));
        assert_eq!(links.resolve(&c2.to_base62()), Some("https://example.com/b"));
        assert_eq!(links.len(), 2);
    }

    #[test]
    fn resolve_is_case_insensitive_and_trims() {
        let mut links = ShortLinks::new();
        let code = links.insert("https://example.com/x");
        let raw = code.to_base62();
        assert_eq!(links.resolve(&raw.to_uppercase()), Some("https://example.com/x"));
        assert_eq!(links.resolve(&format!("  {raw} ")), Some("https://example.com/x"));
    }

    #[test]
    fn unknown_code_is_none() {
        let links = ShortLinks::new();
        assert_eq!(links.resolve("zzzzzz"), None);
        assert_eq!(links.hits("zzzzzz"), None);
        assert!(links.is_empty());
        assert_eq!(links.total_hits(), 0);
    }

    #[test]
    fn insert_opt_respects_max_links() {
        let mut links = ShortLinks::new();
        // Shrink the ceiling by filling just below it using a temporary store
        // with the real const: use a wrapper that stops after MAX_LINKS.
        for _ in 0..MAX_LINKS {
            assert!(links.insert_opt("https://example.com/fill").is_some());
        }
        assert!(links.insert_opt("https://example.com/over").is_none());
        assert_eq!(links.len(), MAX_LINKS);
    }
}
