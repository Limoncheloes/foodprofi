"""Unit tests for procurement routing service.

These tests call the routing functions directly with mocked objects,
not through the HTTP API.
"""
import uuid
import pytest
from unittest.mock import MagicMock

from app.services.routing import find_best_rule, apply_routing


def make_rule(keyword: str, buyer_id=None, category_id=None):
    rule = MagicMock()
    rule.keyword = keyword
    rule.buyer_id = buyer_id or uuid.uuid4()
    rule.category_id = category_id
    return rule


def make_item(raw_name=None, catalog_name=None, is_catalog=True, category_buyer_id=None):
    item = MagicMock()
    item.raw_name = raw_name
    item.is_catalog_item = is_catalog
    item.buyer_id = None
    item.category_id = None
    item.status = "pending_curator"
    if is_catalog and catalog_name:
        item.catalog_item = MagicMock()
        item.catalog_item.name = catalog_name
        item.catalog_item.category = MagicMock()
        item.catalog_item.category.default_buyer_id = category_buyer_id
        item.catalog_item.category.id = uuid.uuid4()
    else:
        item.catalog_item = None
    return item


# --- find_best_rule ---

def test_find_best_rule_returns_longest_matching_keyword():
    rules = [
        make_rule("говядина"),
        make_rule("говядина без кости"),
    ]
    result = find_best_rule("Говядина без кости 1кг", rules)
    assert result.keyword == "говядина без кости"


def test_find_best_rule_case_insensitive():
    rules = [make_rule("МОЛОКО")]
    result = find_best_rule("молоко 1л", rules)
    assert result is not None


def test_find_best_rule_returns_none_if_no_match():
    rules = [make_rule("говядина")]
    result = find_best_rule("картофель 5кг", rules)
    assert result is None


def test_find_best_rule_empty_rules():
    result = find_best_rule("говядина", [])
    assert result is None


# --- apply_routing ---

def test_apply_routing_catalog_item_with_default_buyer():
    buyer_id = uuid.uuid4()
    item = make_item(catalog_name="Говядина", is_catalog=True, category_buyer_id=buyer_id)
    apply_routing(item, rules=[])
    assert item.buyer_id == buyer_id
    assert item.status == "assigned"


def test_apply_routing_catalog_item_no_default_buyer_falls_to_rules():
    buyer_id = uuid.uuid4()
    item = make_item(catalog_name="Говядина", is_catalog=True, category_buyer_id=None)
    rules = [make_rule("говядина", buyer_id=buyer_id)]
    apply_routing(item, rules=rules)
    assert item.buyer_id == buyer_id
    assert item.status == "assigned"


def test_apply_routing_catalog_item_no_match_becomes_pending_curator():
    item = make_item(catalog_name="Говядина", is_catalog=True, category_buyer_id=None)
    apply_routing(item, rules=[])
    assert item.status == "pending_curator"
    assert item.buyer_id is None


def test_apply_routing_raw_name_matches_rule():
    buyer_id = uuid.uuid4()
    item = make_item(raw_name="Ложки пластиковые", is_catalog=False)
    rules = [make_rule("ложки", buyer_id=buyer_id)]
    apply_routing(item, rules=rules)
    assert item.buyer_id == buyer_id
    assert item.status == "assigned"


def test_apply_routing_raw_name_no_match_becomes_pending_curator():
    item = make_item(raw_name="Ложки пластиковые", is_catalog=False)
    apply_routing(item, rules=[])
    assert item.status == "pending_curator"
