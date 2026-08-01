"""Tests for admin dashboard keyboards, including the broadcast feature."""

from __future__ import annotations

from keyboards.admin_keyboard import (
    broadcast_confirm_keyboard,
    broadcast_preview_keyboard,
    broadcast_segment_keyboard,
    overview_keyboard,
)


def test_broadcast_segment_keyboard_builds_one_row_per_segment():
    keyboard = broadcast_segment_keyboard([
        ("all", "همه‌ی کاربران", 230),
        ("never_subscribed", "هرگز مشترک نشده", 127),
    ])
    rows = keyboard.inline_keyboard
    assert rows[0][0].callback_data == "admin:bc:seg:all"
    assert "230" in rows[0][0].text
    assert rows[1][0].callback_data == "admin:bc:seg:never_subscribed"
    assert rows[-1][0].callback_data == "admin:home"


def test_broadcast_preview_keyboard_has_test_send_and_cancel():
    keyboard = broadcast_preview_keyboard()
    callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert callbacks == ["admin:bc:test", "admin:bc:go", "admin:bc:cancel"]


def test_broadcast_confirm_keyboard_has_confirm_and_cancel():
    keyboard = broadcast_confirm_keyboard()
    callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert callbacks == ["admin:bc:go:confirm", "admin:bc:cancel"]


def test_overview_keyboard_includes_broadcast_entry():
    keyboard = overview_keyboard()
    callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert "admin:bc" in callbacks
