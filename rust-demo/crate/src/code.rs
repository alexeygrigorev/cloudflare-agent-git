//! Base62 codes for short links.
//!
//! Codes are dense u64 counters rendered in base62 with a fixed alphabet so
//! they are short, URL-safe and case-insensitive on lookup (normalization is
//! the store's job, see [`crate::ShortLinks::resolve`]).

/// Alphabet used for base62 rendering: digits, then lowercase, then uppercase.
const ALPHABET: &[u8] = b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

const BASE: u64 = ALPHABET.len() as u64;

/// A dense short-link identifier.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Code(u64);

impl Code {
    /// Wraps a raw counter value.
    pub fn new(raw: u64) -> Code {
        Code(raw)
    }

    /// Raw counter value.
    pub fn raw(self) -> u64 {
        self.0
    }

    /// Renders the code in base62 (e.g. `Code(61)` -> `"Z"`, `Code(62)` -> `"10"`).
    pub fn to_base62(self) -> String {
        if self.0 == 0 {
            return "0".to_string();
        }
        let mut digits = Vec::new();
        let mut n = self.0;
        while n > 0 {
            digits.push(ALPHABET[(n % BASE) as usize]);
            n /= BASE;
        }
        digits.reverse();
        String::from_utf8(digits).expect("base62 alphabet is ASCII")
    }
}

/// Parses a base62 string back into a [`Code`].
///
/// Accepts any case: `parse("10")` and `parse("1O")` (digit one, capital O)
/// both decode, but mixed garbage like `"1O_"` fails. `None` on overflow or
/// invalid characters.
pub fn parse_base62(s: &str) -> Option<Code> {
    if s.is_empty() {
        return None;
    }
    let mut acc: u64 = 0;
    for ch in s.bytes() {
        let digit = match ch {
            b'0'..=b'9' => ch - b'0',
            b'a'..=b'z' => ch - b'a' + 10,
            b'A'..=b'Z' => ch - b'A' + 36,
            _ => return None,
        } as u64;
        acc = acc.checked_mul(BASE)?.checked_add(digit)?;
    }
    Some(Code(acc))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_encodes() {
        assert_eq!(Code::new(0).to_base62(), "0");
        assert_eq!(parse_base62("0"), Some(Code::new(0)));
    }

    #[test]
    fn first_alphabet_digit_boundaries() {
        assert_eq!(Code::new(9).to_base62(), "9");
        assert_eq!(Code::new(10).to_base62(), "a");
        assert_eq!(Code::new(35).to_base62(), "z");
        assert_eq!(Code::new(36).to_base62(), "A");
        assert_eq!(Code::new(61).to_base62(), "Z");
        assert_eq!(Code::new(62).to_base62(), "10");
    }

    #[test]
    fn round_trip_examples() {
        for raw in [0u64, 1, 61, 62, 3843, 3844, 238_327, u32::MAX as u64] {
            let code = Code::new(raw);
            assert_eq!(parse_base62(&code.to_base62()), Some(code));
        }
    }

    #[test]
    fn rejects_garbage() {
        assert_eq!(parse_base62(""), None);
        assert_eq!(parse_base62("ab_c"), None);
        assert_eq!(parse_base62("-1"), None);
    }
}
