//! Aggregate reporting over a [`ShortLinks`] store.

use crate::{code::parse_base62, ShortLinks};

/// One-line human-readable summary of the whole store.
pub fn summary(links: &ShortLinks) -> String {
    format!(
        "links={} total_hits={}",
        links.len(),
        links.total_hits()
    )
}

/// Top-N URLs by hit count, descending. Ties break by numeric code value
/// (equivalently insertion order, since codes are dense counters).
pub fn top_links(links: &ShortLinks, n: usize) -> Vec<(String, String, u64)> {
    let mut rows: Vec<(u64, String, u64)> = Vec::new();
    for code in links.codes() {
        let raw = match parse_base62(code) {
            Some(c) => c.raw(),
            None => continue,
        };
        let url = match links.url_of(code) {
            Some(u) => u.to_string(),
            None => continue,
        };
        let hits = links.hits(code).unwrap_or(0);
        rows.push((raw, url, hits));
    }
    rows.sort_by(|a, b| b.2.cmp(&a.2).then_with(|| a.0.cmp(&b.0)));
    rows.truncate(n);
    rows.into_iter()
        .map(|(raw, url, hits)| (crate::code::Code::new(raw).to_base62(), url, hits))
        .collect()
}
