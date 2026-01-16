import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ctgov_utils import build_params, fetch_nct_ids, iter_study_pages


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.url = "https://clinicaltrials.gov/api/v2/studies"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class CtgovUtilsTests(unittest.TestCase):
    def test_build_params_handles_raw_and_encoded(self):
        raw_query = "query.cond=heart failure&query.term=AREA[DesignAllocation]RANDOMIZED"
        params = build_params(raw_query)
        self.assertEqual(params["query.cond"], "heart failure")
        self.assertEqual(params["query.term"], "AREA[DesignAllocation]RANDOMIZED")

        encoded_query = "query.cond=heart%20failure&query.term=AREA%5BDesignAllocation%5DRANDOMIZED"
        params_encoded = build_params(encoded_query)
        self.assertEqual(params_encoded["query.cond"], "heart failure")
        self.assertEqual(params_encoded["query.term"], "AREA[DesignAllocation]RANDOMIZED")

        prefixed_query = "?query.cond=heart%20failure"
        params_prefixed = build_params(prefixed_query)
        self.assertEqual(params_prefixed["query.cond"], "heart failure")

    def test_iter_study_pages_uses_page_token(self):
        responses = [
            {"studies": [], "totalCount": 3, "nextPageToken": "token-1"},
            {"studies": [], "totalCount": 3},
        ]
        session = Mock()
        session.get.side_effect = [FakeResponse(r) for r in responses]

        pages = list(iter_study_pages(session, {"query.cond": "diabetes"}, page_size=2))
        self.assertEqual(len(pages), 2)

        first_params = session.get.call_args_list[0][1]["params"]
        self.assertEqual(first_params["pageSize"], 2)
        self.assertNotIn("pageToken", first_params)

        second_params = session.get.call_args_list[1][1]["params"]
        self.assertEqual(second_params["pageToken"], "token-1")
        self.assertNotIn("countTotal", second_params)

    def test_fetch_nct_ids_collects_all_pages(self):
        studies_page1 = [
            {"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}}
        ]
        studies_page2 = [
            {"protocolSection": {"identificationModule": {"nctId": "nct00000002"}}}
        ]
        responses = [
            {"studies": studies_page1, "totalCount": 2, "nextPageToken": "token-2"},
            {"studies": studies_page2, "totalCount": 2},
        ]
        session = Mock()
        session.get.side_effect = [FakeResponse(r) for r in responses]

        ncts, total = fetch_nct_ids(
            session, {"query.cond": "asthma"}, page_size=1
        )
        self.assertEqual(total, 2)
        self.assertEqual(ncts, {"NCT00000001", "NCT00000002"})


if __name__ == "__main__":
    unittest.main()
