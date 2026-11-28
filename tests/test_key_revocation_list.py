"""Contracts for the key-revocation-list reader.

Every fixture is signed once, with a fixed seed, and embedded as base64: the
tests never produce a signature, so they carry no signing dependency, and
nothing of the peer's corpus is vendored. The corpus check, which does read
their files, runs only when UIBC_KEY_REVOCATION_CORPUS names a checkout.

A decision this reader answers must not depend on the order two checks happen
to run in, so the tests also pin the order the suite makes part of its
contract: trust before signature, freshness before reading, and reading before
coverage.
"""

from __future__ import annotations

import base64
import json
import os
import sys

import pytest

from uibc_core import cli
from uibc_core import key_revocation_list as krl


FIXTURES = {
    "revoked_in_list": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbeyJlZmZlY3RpdmVGcm9tIjogIjIwMjYt"
        "MTEtMjBUMDc6MDA6MDBaIiwgInRodW1icHJpbnQiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3Zjkz"
        "MjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSJ9XX0sICJzaWciOiAiK3hY"
        "RUIrekR0d1lpdGttYlVCY1hrMy9WVk1EU2FqNGYvVGVTVTVDdElKSUhqV1Rlbzd6T0VZUkYzbHpn"
        "Z0I3NExFaXZjd0I2YzIyT3pnR1VaWHY1Q2c9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTVi"
        "NmNhMTI5NTYzZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFl"
        "IiwgInRodW1icHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNm"
        "N2EwOGRiMGY4MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "covered_no_entry": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJvWFBoeWRUenps"
        "cDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1nOEU5QW1OQU5z"
        "Y0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "key_not_covered": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiMmYzNDdlYTg2NDc4OTI3ODEzOGU3NzRhOWUxM2I3ZjBmYjAzYjg2NmUyZDg5YjRjZWQx"
        "Zjc2MGJiYmNhYmM1YyJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJvWFBoeWRUenps"
        "cDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1nOEU5QW1OQU5z"
        "Y0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "not_yet_effective": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbeyJlZmZlY3RpdmVGcm9tIjogIjIwMjYt"
        "MTEtMjBUMTI6MDA6MDBaIiwgInRodW1icHJpbnQiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3Zjkz"
        "MjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSJ9XX0sICJzaWciOiAiODBM"
        "R3FJWDR3bG1ITWRKWkI2eVpudXFxNEZiVjdYZGZXM29nVVBoVGtWZkxudHlrRUNVYm4zQ3ppRTZG"
        "TkJ0V3FNZm5vVWFRR01aMmNHdXovSmNqRFE9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTVi"
        "NmNhMTI5NTYzZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFl"
        "IiwgInRodW1icHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNm"
        "N2EwOGRiMGY4MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "kept_from_earlier": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFt7ImVmZmVjdGl2ZUZyb20iOiAiMjAyNi0xMS0yMFQwNzowMDowMFoiLCAidGh1"
        "bWJwcmludCI6ICI1NDE4ZWE5ODdjNjYzZTU1ZTU0NjdmOTMyMDA5YTRhOTQxZDg2NWIyODMyNmUx"
        "NTk4MmQ4ODVkYTA0M2E2OTBlIn1dfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAw"
        "OjAwWiIsICJrZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgz"
        "MjZlMTU5ODJkODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92"
        "MSIsICJ0cnVzdGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3"
        "YTA4ZGIwZjgwN2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQi"
        "OiAiMjAyNi0xMS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1w"
        "bGUva2V5cyIsICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0"
        "YTk0MWQ4NjViMjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdi"
        "YjZmNWI4YjdhYjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBk"
        "YXRlIjogIjIwMjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJv"
        "WFBoeWRUenpscDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1n"
        "OEU5QW1OQU5zY0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTVi"
        "NmNhMTI5NTYzZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFl"
        "IiwgInRodW1icHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNm"
        "N2EwOGRiMGY4MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "kept_when_no_longer_covered": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFt7ImVmZmVjdGl2ZUZyb20iOiAiMjAyNi0xMS0yMFQwNzowMDowMFoiLCAidGh1"
        "bWJwcmludCI6ICI1NDE4ZWE5ODdjNjYzZTU1ZTU0NjdmOTMyMDA5YTRhOTQxZDg2NWIyODMyNmUx"
        "NTk4MmQ4ODVkYTA0M2E2OTBlIn1dfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAw"
        "OjAwWiIsICJrZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgz"
        "MjZlMTU5ODJkODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92"
        "MSIsICJ0cnVzdGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3"
        "YTA4ZGIwZjgwN2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQi"
        "OiAiMjAyNi0xMS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1w"
        "bGUva2V5cyIsICJrZXlzQ292ZXJlZCI6IFsiYTQwNjY1MzZjNmExNDc2YzI3YmI2ZjViOGI3YWI0"
        "MTkwNDZjNGQ1ZWI5NGViOWM1ZTM5NjVjOTFjZjdmMTAzMyJdLCAibmV4dFVwZGF0ZSI6ICIyMDI2"
        "LTExLTIwVDIwOjAwOjAwWiIsICJyZXZva2VkIjogW119LCAic2lnIjogIk9TTDRjcHlGcG1RVlhn"
        "cURSVVI3Q01tWDR3L3REWCticTZhcVVaWThLWmhadkkvL2FyVGRiSFQvM2lQd1NSZEFQcTZhcEFR"
        "emMzR2VnUU9XNlIwRENnPT0iLCAic2lnbmVyIjogeyJrZXkiOiAiOTM0M2U1YjZjYTEyOTU2M2Q3"
        "MDRmZDQ5ZDdhNGVhNTA5ZmZjNWQ0ZDY1NDZmZTU1YWU3YjU4MDIxNGRiZTQxZSIsICJ0aHVtYnBy"
        "aW50IjogImFjMTlmOGM4ZDY0NTllMmMzMmJlYmIwZmIwOTE0MjBhZTFhMzIzZjdhMDhkYjBmODA3"
        "YTE5NDdlNWQwMDY4MDIifX19"
    ),
    "untrusted_signer": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbeyJlZmZlY3RpdmVGcm9tIjogIjIwMjYt"
        "MTEtMjBUMDc6MDA6MDBaIiwgInRodW1icHJpbnQiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3Zjkz"
        "MjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSJ9XX0sICJzaWciOiAiMW9o"
        "bjI3M0hYS2dkOEN6OXdLV04rR2VNdEEzOFo1UlZsWWZnWUFxcnZNR1E0b3c1ekU1TXBVWEVTWDEv"
        "M2xpSDdNL0hGYUNRd1pteU5HLzRqdGtWQ0E9PSIsICJzaWduZXIiOiB7ImtleSI6ICJiNTE1ZTNm"
        "YzQwYjI5MzY3M2FkNmViN2U1MTA4MjBiYmZlOTFjNWU2NTVkZWUyZTNkNDM2MjlhMjYzNDRhODJk"
        "IiwgInRodW1icHJpbnQiOiAiOWUwN2IxNmIxZGM3YzBlZGZmM2Y0NTdhZGM2NTk0NTFmNGVjYThm"
        "Yzg1MjhlODZkZjg3NmRkMmY0YWRlNjQ0NCJ9fX0="
    ),
    "claimed_thumbprint": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAiejE2MDJGWHQxWjdC"
        "WGRqQnRVSzB6OXlkZHYvMzl0UVdNUFlUNmVpSVNNT281L0tjbklBSFArclpRRDB5cHVxOUJVcm9o"
        "d29KUnI1QUNEeXdlVVllQUE9PSIsICJzaWduZXIiOiB7ImtleSI6ICJiNTE1ZTNmYzQwYjI5MzY3"
        "M2FkNmViN2U1MTA4MjBiYmZlOTFjNWU2NTVkZWUyZTNkNDM2MjlhMjYzNDRhODJkIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "forged_signature": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbeyJlZmZlY3RpdmVGcm9tIjogIjIwMjYt"
        "MTEtMjBUMDc6MDA6MDBaIiwgInRodW1icHJpbnQiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3Zjkz"
        "MjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSJ9XX0sICJzaWciOiAiODBM"
        "R3FJWDR3bG1ITWRKWkI2eVpudXFxNEZiVjdYZGZXM29nVVBoVGtWZkxudHlrRUNVYm4zQ3ppRTZG"
        "TkJ0V3FNZm5vVWFRR01aMmNHdXovSmNqRFE9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTVi"
        "NmNhMTI5NTYzZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFl"
        "IiwgInRodW1icHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNm"
        "N2EwOGRiMGY4MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "older_than_accepted": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0yMFQwODozMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJvWFBoeWRUenps"
        "cDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1nOEU5QW1OQU5z"
        "Y0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "at_last_accepted": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0yMFQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJvWFBoeWRUenps"
        "cDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1nOEU5QW1OQU5z"
        "Y0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "stale": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQyMDowMDow"
        "MVoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJvWFBoeWRUenps"
        "cDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1nOEU5QW1OQU5z"
        "Y0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "at_next_update": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQyMDowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJvWFBoeWRUenps"
        "cDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1nOEU5QW1OQU5z"
        "Y0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "shape_instant": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMCswMDowMCIsICJpc3N1ZXIiOiAiaHR0cHM6Ly9pc3N1ZXIuZXhhbXBsZS9r"
        "ZXlzIiwgImtleXNDb3ZlcmVkIjogWyI1NDE4ZWE5ODdjNjYzZTU1ZTU0NjdmOTMyMDA5YTRhOTQx"
        "ZDg2NWIyODMyNmUxNTk4MmQ4ODVkYTA0M2E2OTBlIiwgImE0MDY2NTM2YzZhMTQ3NmMyN2JiNmY1"
        "YjhiN2FiNDE5MDQ2YzRkNWViOTRlYjljNWUzOTY1YzkxY2Y3ZjEwMzMiXSwgIm5leHRVcGRhdGUi"
        "OiAiMjAyNi0xMS0yMFQyMDowMDowMFoiLCAicmV2b2tlZCI6IFtdfSwgInNpZyI6ICJ6Um9YUGh5"
        "ZFR6emxwOHN1eEp0dXNLMlM4dzlvWDhVZ0xza3JiSjJDd0hYazFiQ1lXNWhTMnd1T2owbWc4RTlB"
        "bU5BTnNjQ1VqZHRnZEJNVjB0SzFBZz09IiwgInNpZ25lciI6IHsia2V5IjogIjkzNDNlNWI2Y2Ex"
        "Mjk1NjNkNzA0ZmQ0OWQ3YTRlYTUwOWZmYzVkNGQ2NTQ2ZmU1NWFlN2I1ODAyMTRkYmU0MWUiLCAi"
        "dGh1bWJwcmludCI6ICJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4"
        "ZGIwZjgwN2ExOTQ3ZTVkMDA2ODAyIn19fQ=="
    ),
    "shape_key": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAielJvWFBoeWRUenps"
        "cDhzdXhKdHVzSzJTOHc5b1g4VWdMc2tyYkoyQ3dIWGsxYkNZVzVoUzJ3dU9qMG1nOEU5QW1OQU5z"
        "Y0NVamR0Z2RCTVYwdEsxQWc9PSIsICJzaWduZXIiOiB7ImtleSI6ICJ6ejQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
    "shape_sig": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAibm90IGJhc2U2NCEh"
        "IiwgInNpZ25lciI6IHsia2V5IjogIjkzNDNlNWI2Y2ExMjk1NjNkNzA0ZmQ0OWQ3YTRlYTUwOWZm"
        "YzVkNGQ2NTQ2ZmU1NWFlN2I1ODAyMTRkYmU0MWUiLCAidGh1bWJwcmludCI6ICJhYzE5ZjhjOGQ2"
        "NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgwN2ExOTQ3ZTVkMDA2ODAyIn19"
        "fQ=="
    ),
    "conflict_duplicate": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbeyJlZmZlY3RpdmVGcm9tIjogIjIwMjYt"
        "MTEtMjBUMDc6MDA6MDBaIiwgInRodW1icHJpbnQiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3Zjkz"
        "MjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSJ9LCB7ImVmZmVjdGl2ZUZy"
        "b20iOiAiMjAyNi0xMS0yMFQxMjowMDowMFoiLCAidGh1bWJwcmludCI6ICI1NDE4ZWE5ODdjNjYz"
        "ZTU1ZTU0NjdmOTMyMDA5YTRhOTQxZDg2NWIyODMyNmUxNTk4MmQ4ODVkYTA0M2E2OTBlIn1dfSwg"
        "InNpZyI6ICJjNmVtdlZCRE43ZVhLZ1FybGRPSHVmV1djNGxkYjJ0QXlCL0ZEQm95L1BNMmJjaThJ"
        "MHhpWXpwd1M3SEQ1ekJtWE1IZERwTnhFUlRPdkRiRHdaV0pCQT09IiwgInNpZ25lciI6IHsia2V5"
        "IjogIjkzNDNlNWI2Y2ExMjk1NjNkNzA0ZmQ0OWQ3YTRlYTUwOWZmYzVkNGQ2NTQ2ZmU1NWFlN2I1"
        "ODAyMTRkYmU0MWUiLCAidGh1bWJwcmludCI6ICJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkx"
        "NDIwYWUxYTMyM2Y3YTA4ZGIwZjgwN2ExOTQ3ZTVkMDA2ODAyIn19fQ=="
    ),
    "forged_after_signing": (
        "eyJjYXNlIjogeyJsaXN0IjogImxpc3QuanNvbiIsICJub3ciOiAiMjAyNi0xMS0yMFQwOTowMDow"
        "MFoiLCAicHJpb3IiOiB7ImFjY2VwdGVkSXNzdWVkQXQiOiAiMjAyNi0xMS0xOVQwODowMDowMFoi"
        "LCAic2VlbiI6IFtdfSwgInF1ZXJ5IjogeyJhdCI6ICIyMDI2LTExLTIwVDA5OjAwOjAwWiIsICJr"
        "ZXkiOiAiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjViMjgzMjZlMTU5ODJk"
        "ODg1ZGEwNDNhNjkwZSJ9LCAic3VpdGUiOiAia2V5LXJldm9jYXRpb24tbGlzdC92MSIsICJ0cnVz"
        "dGVkIjogWyJhYzE5ZjhjOGQ2NDU5ZTJjMzJiZWJiMGZiMDkxNDIwYWUxYTMyM2Y3YTA4ZGIwZjgw"
        "N2ExOTQ3ZTVkMDA2ODAyIl19LCAibGlzdCI6IHsibGlzdCI6IHsiaXNzdWVkQXQiOiAiMjAyNi0x"
        "MS0yMFQwODowMDowMFoiLCAiaXNzdWVyIjogImh0dHBzOi8vaXNzdWVyLmV4YW1wbGUva2V5cyIs"
        "ICJrZXlzQ292ZXJlZCI6IFsiNTQxOGVhOTg3YzY2M2U1NWU1NDY3ZjkzMjAwOWE0YTk0MWQ4NjVi"
        "MjgzMjZlMTU5ODJkODg1ZGEwNDNhNjkwZSIsICJhNDA2NjUzNmM2YTE0NzZjMjdiYjZmNWI4Yjdh"
        "YjQxOTA0NmM0ZDVlYjk0ZWI5YzVlMzk2NWM5MWNmN2YxMDMzIl0sICJuZXh0VXBkYXRlIjogIjIw"
        "MjYtMTEtMjBUMjA6MDA6MDBaIiwgInJldm9rZWQiOiBbXX0sICJzaWciOiAiK3hYRUIrekR0d1lp"
        "dGttYlVCY1hrMy9WVk1EU2FqNGYvVGVTVTVDdElKSUhqV1Rlbzd6T0VZUkYzbHpnZ0I3NExFaXZj"
        "d0I2YzIyT3pnR1VaWHY1Q2c9PSIsICJzaWduZXIiOiB7ImtleSI6ICI5MzQzZTViNmNhMTI5NTYz"
        "ZDcwNGZkNDlkN2E0ZWE1MDlmZmM1ZDRkNjU0NmZlNTVhZTdiNTgwMjE0ZGJlNDFlIiwgInRodW1i"
        "cHJpbnQiOiAiYWMxOWY4YzhkNjQ1OWUyYzMyYmViYjBmYjA5MTQyMGFlMWEzMjNmN2EwOGRiMGY4"
        "MDdhMTk0N2U1ZDAwNjgwMiJ9fX0="
    ),
}



def _materialise(tmp_path, name):
    """Write one fixture's case and list beside it, and return the case path."""
    blob = base64.b64decode(FIXTURES[name])
    document = json.loads(blob)
    tmp_path.mkdir(parents=True, exist_ok=True)
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(document["case"]), encoding="utf-8")
    (tmp_path / "list.json").write_text(json.dumps(document["list"]), encoding="utf-8")
    return str(case_path)


def answer(case_path):
    result = krl.judge_case_or_refusal(case_path)
    return result["decision"], result["reason"]


#: name -> (decision, reason): every rule and every control, one row each.
EXPECTED = {
    "revoked_in_list": ("revoked", "revoked_in_list"),
    "covered_no_entry": ("not_revoked", "covered_no_entry"),
    "key_not_covered": ("no_statement", "key_not_covered"),
    "not_yet_effective": ("not_revoked", "revocation_not_yet_effective"),
    "kept_from_earlier": ("revoked", "revoked_kept_from_earlier_list"),
    "kept_when_no_longer_covered": ("revoked", "revoked_kept_from_earlier_list"),
    "untrusted_signer": ("rejected", "signer_not_trusted"),
    "claimed_thumbprint": ("rejected", "signer_not_trusted"),
    "forged_signature": ("rejected", "list_signature_invalid"),
    "older_than_accepted": ("rejected", "list_older_than_accepted"),
    "at_last_accepted": ("not_revoked", "covered_no_entry"),
    "stale": ("stale", "list_stale"),
    "at_next_update": ("not_revoked", "covered_no_entry"),
    "shape_instant": ("rejected", "key_revocation_list_shape"),
    "shape_key": ("rejected", "key_revocation_list_shape"),
    "shape_sig": ("rejected", "key_revocation_list_shape"),
    "conflict_duplicate": ("rejected", "key_revocation_list_conflict"),
    "forged_after_signing": ("rejected", "list_signature_invalid"),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_case_answers_as_the_suite_says(tmp_path, name):
    case_path = _materialise(tmp_path, name)
    assert answer(case_path) == EXPECTED[name]


def test_the_five_decisions_carry_the_contract_exit_codes():
    assert krl.EXIT_FOR == {
        "revoked": 0,
        "not_revoked": 1,
        "no_statement": 2,
        "rejected": 3,
        "stale": 4,
    }
    assert set(krl.EXIT_FOR) == set(krl.DECISIONS)


def test_a_list_names_the_rule_it_was_answered_by(tmp_path):
    """A decision is auditable: the rule that produced it is returned with it."""
    revoked = krl.judge_case_or_refusal(_materialise(tmp_path / "a", "revoked_in_list"))
    kept = krl.judge_case_or_refusal(_materialise(tmp_path / "b", "kept_from_earlier"))
    absent = krl.judge_case_or_refusal(_materialise(tmp_path / "c", "key_not_covered"))
    assert revoked["basis"]["rule"] == "in_list"
    assert kept["basis"]["rule"] == "retained"
    assert absent["basis"]["rule"] == "absent"


def test_silence_about_an_uncovered_key_is_not_a_statement(tmp_path):
    """The distinction the suite is built on: no_statement is not not_revoked."""
    covered = answer(_materialise(tmp_path / "a", "covered_no_entry"))
    uncovered = answer(_materialise(tmp_path / "b", "key_not_covered"))
    assert covered[0] == "not_revoked"
    assert uncovered[0] == "no_statement"


def test_a_revocation_once_seen_survives_a_later_list_that_omits_it(tmp_path):
    """A newer list cannot launder a revocation by not mentioning it."""
    result = krl.judge_case_or_refusal(_materialise(tmp_path, "kept_from_earlier"))
    assert result["reason"] == "revoked_kept_from_earlier_list"
    assert result["basis"]["effectiveFrom"].startswith("2026-11-20T07:00:00")


def test_a_claim_of_a_trusted_thumbprint_does_not_make_a_key_trusted(tmp_path):
    """Trust is recomputed from the key, never read from the envelope."""
    result = krl.judge_case_or_refusal(_materialise(tmp_path, "claimed_thumbprint"))
    assert result["reason"] == "signer_not_trusted"
    assert result["facts"]["signerThumbprintHonest"] is False
    assert result["facts"]["recomputedThumbprint"] != result["facts"]["claimedThumbprint"]


def test_trust_is_decided_before_the_signature(tmp_path):
    """Check order is part of the contract: an untrusted signer is named first."""
    case_path = _materialise(tmp_path, "forged_signature")
    case_doc = json.loads((tmp_path / "case.json").read_text(encoding="utf-8"))
    case_doc["trusted"] = []
    (tmp_path / "case.json").write_text(json.dumps(case_doc), encoding="utf-8")
    result = krl.judge_case_or_refusal(case_path)
    assert result["reason"] == "signer_not_trusted"
    assert result["facts"]["signatureVerifiesUnderCarriedKey"] is False


def test_a_list_at_the_last_accepted_time_is_not_older(tmp_path):
    assert answer(_materialise(tmp_path, "at_last_accepted")) == (
        "not_revoked",
        "covered_no_entry",
    )


def test_a_list_at_its_next_update_is_still_current(tmp_path):
    assert answer(_materialise(tmp_path, "at_next_update")) == (
        "not_revoked",
        "covered_no_entry",
    )


def test_one_second_past_the_next_update_is_stale(tmp_path):
    assert answer(_materialise(tmp_path, "stale")) == ("stale", "list_stale")


def test_a_removed_revocation_breaks_the_signature(tmp_path):
    """The tamper the suite cares about: a list edited after it was signed."""
    assert answer(_materialise(tmp_path, "forged_after_signing")) == (
        "rejected",
        "list_signature_invalid",
    )


def test_an_instant_in_another_spelling_is_refused_not_compared_as_text(tmp_path):
    """Two spellings of one second must not be compared as text and answered."""
    result = krl.judge_case_or_refusal(_materialise(tmp_path, "shape_instant"))
    assert result["reason"] == "key_revocation_list_shape"
    assert result["detail"] == "issuedAt_not_a_utc_second"


def test_a_key_that_is_not_hex_is_refused(tmp_path):
    result = krl.judge_case_or_refusal(_materialise(tmp_path, "shape_key"))
    assert result["detail"] == "signer_key_not_hex64"


def test_a_signature_that_is_not_base64_is_refused(tmp_path):
    result = krl.judge_case_or_refusal(_materialise(tmp_path, "shape_sig"))
    assert result["detail"] == "sig_not_base64"


def test_two_records_for_one_key_that_disagree_are_refused(tmp_path):
    """The reference reader's last-wins dictionary would answer without saying which."""
    result = krl.judge_case_or_refusal(_materialise(tmp_path, "conflict_duplicate"))
    assert result["reason"] == "key_revocation_list_conflict"
    assert result["detail"].startswith("list.revoked:two_times_for_")


def test_the_declared_facts_are_recomputed_from_the_bytes(tmp_path):
    honest = krl.retained(_materialise(tmp_path / "a", "revoked_in_list"))
    forged = krl.retained(_materialise(tmp_path / "b", "claimed_thumbprint"))
    assert honest == {
        "signerThumbprintHonest": True,
        "signatureVerifiesUnderCarriedKey": True,
    }
    assert forged == {
        "signerThumbprintHonest": False,
        "signatureVerifiesUnderCarriedKey": True,
    }


def test_thumbprint_is_computed_from_the_key_bytes():
    import hashlib

    key_hex = "9343e5b6ca129563d704fd49d7a4ea509ffc5d4d6546fe55ae7b580214dbe41e"
    assert krl.thumbprint(key_hex) == hashlib.sha256(bytes.fromhex(key_hex)).hexdigest()
    with pytest.raises(krl.Refusal):
        krl.thumbprint("zz" * 32)


def _write_corpus(root, names):
    """A tiny corpus in the peer's layout: MANIFEST.json plus one directory per case."""
    entries = []
    for name in names:
        directory = root / "cases" / name
        directory.mkdir(parents=True)
        case_path = _materialise(directory, name)
        entries.append({
            "id": name,
            "path": f"cases/{name}",
            "expected": {"decision": EXPECTED[name][0], "reason": EXPECTED[name][1]},
            "retained": krl.retained(case_path),
        })
    (root / "MANIFEST.json").write_text(json.dumps({"vectors": entries}), encoding="utf-8")


def test_a_corpus_is_judged_member_by_member(tmp_path):
    _write_corpus(tmp_path, ["revoked_in_list", "stale", "key_not_covered"])
    summary = krl.judge_corpus(str(tmp_path))
    assert (summary["members"], summary["conforming"]) == (3, 3)
    assert [r["got"]["decision"] for r in summary["records"]] == [
        "revoked",
        "stale",
        "no_statement",
    ]


def test_a_member_that_differs_is_named_with_the_field_it_differs_on(tmp_path):
    _write_corpus(tmp_path, ["revoked_in_list"])
    manifest_path = tmp_path / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["vectors"][0]["expected"]["reason"] = "covered_no_entry"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    summary = krl.judge_corpus(str(tmp_path))
    assert summary["conforming"] == 0
    assert summary["records"][0]["mismatched"] == ["reason"]


def test_the_cli_answers_one_case_with_the_contract_exit_code(tmp_path, capsys):
    case_path = _materialise(tmp_path / "a", "revoked_in_list")
    argv = ["uibc", "verify-key-revocation-list", "--case", case_path]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
    finally:
        sys.argv = old
    assert exit_info.value.code == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    answer = json.loads(last)
    assert answer["decision"] == "revoked"
    assert answer["reason"] == "revoked_in_list"
    assert answer["exit"] == 0


def test_the_cli_exits_by_the_decision_not_by_pass_or_fail(tmp_path):
    case_path = _materialise(tmp_path, "stale")
    argv = ["uibc", "verify-key-revocation-list", "--case", case_path]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
    finally:
        sys.argv = old
    assert exit_info.value.code == krl.EXIT_FOR["stale"] == 4
