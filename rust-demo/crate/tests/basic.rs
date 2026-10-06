//! Integration tests for the shortlinks store.

use shortlinks::{code::parse_base62, stats, ShortLinks};

fn sample() -> ShortLinks {
    let mut links = ShortLinks::new();
    links.insert("https://example.com/docs");
    links.insert("https://example.com/blog");
    links.insert("https://example.com/repo");
    links
}

#[test]
fn resolves_all_inserted_urls() {
    let links = sample();
    assert_eq!(links.resolve("1"), Some("https://example.com/docs"));
    assert_eq!(links.resolve("2"), Some("https://example.com/blog"));
    assert_eq!(links.resolve("3"), Some("https://example.com/repo"));
    assert_eq!(links.resolve("4"), None);
}

#[test]
fn codes_round_trip_through_base62() {
    let mut links = ShortLinks::new();
    let code = links.insert("https://example.com/round");
    let parsed = parse_base62(&code.to_base62()).expect("valid base62");
    assert_eq!(parsed, code);
    assert_eq!(links.resolve(&parsed.to_base62()), Some("https://example.com/round"));
}

#[test]
fn summary_line_reports_counts() {
    let links = sample();
    assert_eq!(stats::summary(&links), "links=3 total_hits=0");
}

#[test]
fn top_links_is_stable_and_ordered() {
    let links = sample();
    let top = stats::top_links(&links, 2);
    assert_eq!(top.len(), 2);
    // No hits yet anywhere: insertion order (by code) breaks ties.
    assert_eq!(top[0], ("1".to_string(), "https://example.com/docs".to_string(), 0));
    assert_eq!(top[1], ("2".to_string(), "https://example.com/blog".to_string(), 0));
}
