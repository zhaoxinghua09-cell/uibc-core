"""The revocation-list reader, held to its own signed fixtures.

The peer's shipped corpus is judged separately (see
``tests/test_revocation_list_corpus.py``, which runs only when
``UIBC_REVOCATION_CORPUS`` points at a checkout), so this file neither venders
third-party fixtures nor needs the network. It checks the checks: what the fold
installs, what it refuses, and which code it refuses with.

The fixtures were signed once with fixed seeds and are embedded as bytes, so
these tests carry no signer and no crypto dependency beyond the package's own
verifier.
"""

import base64
import json

import pytest

from uibc_core import revocation_list as rl

# Signing keys: fixed seeds; the public ids below are what a verifier pins.
ROOT_A = "10ba682c8ad13513971e8b56881aab8bd702bb807796eca81932c735a94d6e6d"
ROOT_B = "1325b850c2871916eae203f0efc3c8987f64e5e3cdb27679e6d1fa97808357e6"
ROOT_C = "6c8f8607dbe87077a62a2990ce07d94aaf749df76f87b98eb786a6d10f030765"

# Signed lists, produced once and embedded so the tests need no signer.
_FIXTURES_B64 = {
    "L1": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbXQogIH0sCiAgInNpZyI6ICJyK2VFQVd1QmFUOWpoT05rNjZYbFVLVkpJYlZsV0RRbEVXUWEvanozMGdtSzBzV0FPU3hQSnF2Vk1FT3pQNi9mcFdnVnVWbGNobjZMb1NLRmNVRHBCQT09Igp9",
    "L2": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDIsCiAgICAicHJldmlvdXMiOiAic2hhMjU2OjZlMGJkZjc0YjRkMzcxMmY2NjYxOTE0YjM5YWJmYWI5YTBjZjE1ODVkMjA1ODY1Mzk1MjBhMTFmN2ViYTZjMjAiLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDJUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbCiAgICAgIHsKICAgICAgICAia2luZCI6ICJhZ2VudCIsCiAgICAgICAgImlkIjogImFnZW50OmFscGhhIiwKICAgICAgICAicmV2b2tlZEF0IjogIjIwMjYtMDUtMzFUMDA6MDA6MDBaIgogICAgICB9CiAgICBdCiAgfSwKICAic2lnIjogIlJKSlFIclpHbzVVUjBUOXRpT0pHeFFKZUt3TFpZSnhaOFBkWnloQitrbVo5TmViSU1nQzdaQkNrU2lDeTUyODVVYnlremVka3FnUnlzRVVPSHk0OUJnPT0iCn0=",
    "L2_WRONGPREV": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDIsCiAgICAicHJldmlvdXMiOiAic2hhMjU2OjAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAiLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDJUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbXQogIH0sCiAgInNpZyI6ICJFTlFvNGRiT042OHRwT04rTXNrM29HekxrTjR5MW1FL3ZlYnYzRGErWmxXcjhLall2b3VXS2orSjM0YUkxenIxUGV1bnY3Y2QyenVKOU5HMWtTT1ZCdz09Igp9",
    "L3_DROP": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDMsCiAgICAicHJldmlvdXMiOiAic2hhMjU2OmQwNzJmOTE0Y2ZmMzMyNjg4YmJhYmIxODAxMjFhYzJhNjFkZjBmYTY4MTI0NGNmYmVkMDA2MzUzMzlhNmIwYmUiLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDNUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbXQogIH0sCiAgInNpZyI6ICJHMGFkYkc3cFRQRmdiWkQ3dkF1V1Q4SHpTQWcyVmNtSEdGQ3hPY0YwOFc2T1ZzZUNBYW5sTHNlT3Z6QVNjUlVZS0RkUE82eDNtdUpycjRhNGtOV2ZCZz09Igp9",
    "L_BY_C": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiRjh0NSt5dEJJUEt4N0dYa0dZMXVDTEtPZ1QvckFlU2tBSU9iaGVHQWdNND0iLAogICAgImVudHJpZXMiOiBbXQogIH0sCiAgInNpZyI6ICJWUnRnQk9NaHNUdCs3b0VFelVBeFFlUDVWZEJsb3g4Qld4MjVzRUNSWUxvWSt2WTRjK3BGWDVDTDMrTi9vclZnOGVZSElXY1JTcnlZYVREZURMQmNDZz09Igp9",
    "L1_BADSIG": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbXQogIH0sCiAgInNpZyI6ICJydWVFQVd1QmFUOWpoT05rNjZYbFVLVkpJYlZsV0RRbEVXUWEvanozMGdtSzBzV0FPU3hQSnF2Vk1FT3pQNi9mcFdnVnVWbGNobjZMb1NLRmNVRHBCQT09Igp9",
    "L_ROT": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDIsCiAgICAicHJldmlvdXMiOiAic2hhMjU2OjZlMGJkZjc0YjRkMzcxMmY2NjYxOTE0YjM5YWJmYWI5YTBjZjE1ODVkMjA1ODY1Mzk1MjBhMTFmN2ViYTZjMjAiLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDJUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbCiAgICAgIHsKICAgICAgICAia2luZCI6ICJrZXkiLAogICAgICAgICJpZCI6ICIxMGJhNjgyYzhhZDEzNTEzOTcxZThiNTY4ODFhYWI4YmQ3MDJiYjgwNzc5NmVjYTgxOTMyYzczNWE5NGQ2ZTZkIiwKICAgICAgICAicmV2b2tlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICAgICAic3VjY2Vzc29yIjogIm9KcWw5SHBuV1lBditWWDQzQzBxRktYSm5TTytsL2hrRW4vNU9EUlZwUEE9IgogICAgICB9CiAgICBdCiAgfSwKICAic2lnIjogImpxWnhMU3NJN2lMUkE0TURKZEhUNjdsUHl6R1JlWWRQV0NoLzlIUTJaaWNXekd2V0k2YzJlQS83Qk15aVZGdjRBVGpMR3hCN05tQkgvRUI0Ri9QL0R3PT0iCn0=",
    "L_BY_B": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDMsCiAgICAicHJldmlvdXMiOiAic2hhMjU2OjU3NjAyNDEyNTdhYmM2OGJmYjVjNzQ1MjUwZmFlOTE5NGVjNDJiMmQ5ODg2MjM1NDQ5MDkxYWVhOWYyOTBjNzYiLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDNUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAib0pxbDlIcG5XWUF2K1ZYNDNDMHFGS1hKblNPK2wvaGtFbi81T0RSVnBQQT0iLAogICAgImVudHJpZXMiOiBbCiAgICAgIHsKICAgICAgICAia2luZCI6ICJrZXkiLAogICAgICAgICJpZCI6ICIxMGJhNjgyYzhhZDEzNTEzOTcxZThiNTY4ODFhYWI4YmQ3MDJiYjgwNzc5NmVjYTgxOTMyYzczNWE5NGQ2ZTZkIiwKICAgICAgICAicmV2b2tlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICAgICAic3VjY2Vzc29yIjogIm9KcWw5SHBuV1lBditWWDQzQzBxRktYSm5TTytsL2hrRW4vNU9EUlZwUEE9IgogICAgICB9CiAgICBdCiAgfSwKICAic2lnIjogIlBvTDNsdy9BYmVSMUViUk95bWtlWVdFbXNCYk5VMnlDUGFTYmNtOXVyb3ptR29VSWE4cWdGd2VNMmxnN2ZzN1RNaml2NkhwUDkwd2xGRUxkOHRlRENRPT0iCn0=",
    "M_MEMBERS": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iCiAgfSwKICAic2lnIjogInIrZUVBV3VCYVQ5amhPTms2NlhsVUtWSkliVmxXRFFsRVdRYS9qejMwZ21LMHNXQU9TeFBKcXZWTUVPelA2L2ZwV2dWdVZsY2huNkxvU0tGY1VEcEJBPT0iCn0=",
    "M_TYPE": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9leGFtcGxlLnRlc3Qvb3RoZXIiLAogICAgImxpc3RJZCI6ICJwcm9iaXR5LXJldm9jYXRpb25zIiwKICAgICJzZXEiOiAxLAogICAgInByZXZpb3VzIjogbnVsbCwKICAgICJpc3N1ZWRBdCI6ICIyMDI2LTA2LTAxVDAwOjAwOjAwWiIsCiAgICAiaXNzdWVyS2V5IjogIjBFcXlNblFydEtzNkUyaTlSaFhrNXRBaVNyY2FBV3V2aFNDak1zbDNoemM9IiwKICAgICJlbnRyaWVzIjogW10KICB9LAogICJzaWciOiAicitlRUFXdUJhVDlqaE9OazY2WGxVS1ZKSWJWbFdEUWxFV1FhL2p6MzBnbUswc1dBT1N4UEpxdlZNRU96UDYvZnBXZ1Z1VmxjaG42TG9TS0ZjVURwQkE9PSIKfQ==",
    "M_SEQ_BOOL": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IHRydWUsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbXQogIH0sCiAgInNpZyI6ICJyK2VFQVd1QmFUOWpoT05rNjZYbFVLVkpJYlZsV0RRbEVXUWEvanozMGdtSzBzV0FPU3hQSnF2Vk1FT3pQNi9mcFdnVnVWbGNobjZMb1NLRmNVRHBCQT09Igp9",
    "M_KIND": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbCiAgICAgIHsKICAgICAgICAia2luZCI6ICJyb2JvdCIsCiAgICAgICAgImlkIjogImFnZW50OmFscGhhIiwKICAgICAgICAicmV2b2tlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIgogICAgICB9CiAgICBdCiAgfSwKICAic2lnIjogInIrZUVBV3VCYVQ5amhPTms2NlhsVUtWSkliVmxXRFFsRVdRYS9qejMwZ21LMHNXQU9TeFBKcXZWTUVPelA2L2ZwV2dWdVZsY2huNkxvU0tGY1VEcEJBPT0iCn0=",
    "M_KEY31": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h3PT0iLAogICAgImVudHJpZXMiOiBbXQogIH0sCiAgInNpZyI6ICJyK2VFQVd1QmFUOWpoT05rNjZYbFVLVkpJYlZsV0RRbEVXUWEvanozMGdtSzBzV0FPU3hQSnF2Vk1FT3pQNi9mcFdnVnVWbGNobjZMb1NLRmNVRHBCQT09Igp9",
    "M_NL": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGtcbjV0QWlTcmNhQVd1dmhTQ2pNc2wzaHpjPSIsCiAgICAiZW50cmllcyI6IFtdCiAgfSwKICAic2lnIjogInIrZUVBV3VCYVQ5amhPTms2NlhsVUtWSkliVmxXRFFsRVdRYS9qejMwZ21LMHNXQU9TeFBKcXZWTUVPelA2L2ZwV2dWdVZsY2huNkxvU0tGY1VEcEJBPT0iCn0=",
    "M_ORDER": "ewogICJib2R5IjogewogICAgInR5cGUiOiAiaHR0cHM6Ly9wcm9iaXR5YWkuZ2l0aHViLmlvL2FnZW50LWV2aWRlbmNlLXZlY3RvcnMvcHJlZGljYXRlL3YxL3Jldm9jYXRpb24tbGlzdCIsCiAgICAibGlzdElkIjogInByb2JpdHktcmV2b2NhdGlvbnMiLAogICAgInNlcSI6IDEsCiAgICAicHJldmlvdXMiOiBudWxsLAogICAgImlzc3VlZEF0IjogIjIwMjYtMDYtMDFUMDA6MDA6MDBaIiwKICAgICJpc3N1ZXJLZXkiOiAiMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6Yz0iLAogICAgImVudHJpZXMiOiBbCiAgICAgIHsKICAgICAgICAia2luZCI6ICJhZ2VudCIsCiAgICAgICAgImlkIjogImFnZW50OmIiLAogICAgICAgICJyZXZva2VkQXQiOiAiMjAyNi0wNi0wMVQwMDowMDowMFoiCiAgICAgIH0sCiAgICAgIHsKICAgICAgICAia2luZCI6ICJhZ2VudCIsCiAgICAgICAgImlkIjogImFnZW50OmEiLAogICAgICAgICJyZXZva2VkQXQiOiAiMjAyNi0wNi0wMVQwMDowMDowMFoiCiAgICAgIH0KICAgIF0KICB9LAogICJzaWciOiAicitlRUFXdUJhVDlqaE9OazY2WGxVS1ZKSWJWbFdEUWxFV1FhL2p6MzBnbUswc1dBT1N4UEpxdlZNRU96UDYvZnBXZ1Z1VmxjaG42TG9TS0ZjVURwQkE9PSIKfQ==",
}

FIXTURES = {name: base64.b64decode(value) for name, value in _FIXTURES_B64.items()}


def _chain(*names):
    return [FIXTURES[n] for n in names]


def test_an_empty_first_list_is_in_force():
    got = rl.verify_chain([ROOT_A], _chain("L1"))
    assert got["verdict"] == "valid"
    assert got["reason"] == "in_force"
    assert got["index"] is None
    assert got["state"]["seq"] == 1
    assert got["state"]["roots"] == [ROOT_A]
    assert got["state"]["revoked"] == {k: [] for k in rl.KINDS}


def test_the_digest_is_the_jcs_form_of_the_body():
    got = rl.verify_chain([ROOT_A], _chain("L1"))
    body = json.loads(FIXTURES["L1"])["body"]
    assert got["listDigests"] == [rl.list_digest(body)]
    assert got["state"]["head"] == rl.list_digest(body)


def test_a_second_list_carries_the_first_entry_forward():
    got = rl.verify_chain([ROOT_A], _chain("L1", "L2"))
    assert got["verdict"] == "valid"
    assert got["state"]["seq"] == 2
    assert got["state"]["revoked"]["agent"] == ["agent:alpha"]


def test_replaying_the_list_in_force_is_a_rollback():
    first = rl.apply(rl.RevocationState([ROOT_A]), FIXTURES["L1"])
    with pytest.raises(rl.Refusal) as excinfo:
        rl.apply(first, FIXTURES["L1"])
    assert str(excinfo.value) == "revocation_list_rollback:1<=1"


def test_skipping_a_sequence_is_a_gap():
    got = rl.verify_chain([ROOT_A], _chain("L2"))
    assert got["reason"] == "revocation_list_gap:2>1"
    assert got["index"] == 0
    assert got["state"]["seq"] == 0


def test_a_successor_naming_another_head_is_refused():
    got = rl.verify_chain([ROOT_A], _chain("L1", "L2_WRONGPREV"))
    assert got["reason"] == "revocation_list_previous_mismatch"
    assert got["index"] == 1
    assert got["state"]["seq"] == 1


def test_a_list_that_drops_an_entry_is_refused_and_the_entry_is_named():
    got = rl.verify_chain([ROOT_A], _chain("L1", "L2", "L3_DROP"))
    assert got["reason"] == "revocation_list_drops_entry:agent:agent:alpha"
    assert got["state"]["revoked"]["agent"] == ["agent:alpha"]


def test_a_key_that_is_not_pinned_is_refused():
    got = rl.verify_chain([ROOT_A], _chain("L_BY_C"))
    assert got["reason"] == "revocation_list_signer_not_a_root"


def test_a_tampered_signature_is_refused():
    got = rl.verify_chain([ROOT_A], _chain("L1_BADSIG"))
    assert got["reason"] == "revocation_list_signature_unverified"


def test_a_retired_root_hands_over_to_its_successor():
    after = rl.verify_chain([ROOT_A], _chain("L1", "L_ROT"))
    assert after["verdict"] == "valid"
    assert after["state"]["roots"] == [ROOT_B]
    got = rl.verify_chain([ROOT_A], _chain("L1", "L_ROT", "L_BY_B"))
    assert got["verdict"] == "valid"
    assert got["state"]["seq"] == 3


def test_the_successor_is_not_pinned_before_the_rotation():
    got = rl.verify_chain([ROOT_B], _chain("L_BY_B"))
    assert got["reason"] == "revocation_list_gap:3>1"


@pytest.mark.parametrize(
    "fixture, reason",
    [
        ("M_MEMBERS", "revocation_list_shape:body_members"),
        ("M_TYPE", "revocation_list_shape:type"),
        ("M_SEQ_BOOL", "revocation_list_shape:seq_not_a_positive_exact_integer"),
        ("M_KIND", "revocation_list_shape:entry_kind_unknown"),
        ("M_KEY31", "revocation_list_shape:issuerKey_not_an_ed25519_key"),
        ("M_NL", "revocation_list_shape:issuerKey_not_canonical_base64"),
        ("M_ORDER", "revocation_list_shape:entries_not_strictly_ascending"),
    ],
)
def test_shape_refusals_name_the_one_thing_they_refuse(fixture, reason):
    got = rl.verify_chain([ROOT_A], _chain(fixture))
    assert got["reason"] == reason
    assert got["state"]["seq"] == 0


def test_an_unreadable_file_is_not_a_shape_finding():
    got = rl.verify_chain([ROOT_A], [b'{"body": '])
    assert got["reason"] == "revocation_list_shape:signed_list_unreadable"
    assert got["listDigests"] == [None]


def test_a_signature_over_another_body_is_refused():
    obj = json.loads(FIXTURES["L1"])
    obj["body"]["issuedAt"] = "2026-06-01T00:00:01Z"
    got = rl.verify_chain([ROOT_A], [json.dumps(obj).encode()])
    assert got["reason"] == "revocation_list_signature_unverified"


def test_a_case_directory_is_judged_from_its_roots_and_files(tmp_path):
    (tmp_path / "roots.json").write_text(json.dumps({"roots": [ROOT_A]}), encoding="utf-8")
    (tmp_path / "list-01.json").write_bytes(FIXTURES["L1"])
    (tmp_path / "list-02.json").write_bytes(FIXTURES["L2"])
    got = rl.judge_case(str(tmp_path))
    assert got["verdict"] == "valid"
    assert got["state"]["revoked"]["agent"] == ["agent:alpha"]
