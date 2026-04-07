import json
import re
import urllib.parse
import requests

from .rpc.encoder import encode_rpc_request, build_request_body
from .rpc.decoder import decode_response
from .rpc.types import RPCMethod, BATCHEXECUTE_URL

class SyncClientCore:
    def __init__(self, cookies_dict):
        self.session = requests.Session()
        
        # Add a realistic User-Agent to avoid generic python-requests blocking
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        })
        
        # Set cookies to the session
        for k, v in cookies_dict.items():
            self.session.cookies.set(k, v, domain=".google.com")
            
        self.csrf_token = None
        self.session_id = None
        self._reqid_counter = 100000
        
        # Auto login on init
        self._fetch_tokens()

    def _fetch_tokens(self):
        """Fetch CSRF and Session ID silently."""
        res = self.session.get("https://notebooklm.google.com/")
        res.raise_for_status()
        
        csrf_match = re.search(r'"SNlM0e":"([^"]+)"', res.text)
        if not csrf_match:
            raise Exception("CSRF token not found. Cookies might be invalid or expired.")
        self.csrf_token = csrf_match.group(1)
        
        sid_match = re.search(r'"FdrFJe":"([^"]+)"', res.text)
        if not sid_match:
            raise Exception("Session ID not found.")
        self.session_id = sid_match.group(1)

    def get_source_ids(self, notebook_id: str) -> list:
        """Helper to get source IDs for chat/artifacts."""
        params = [notebook_id, None, [2], None, 0]
        nb_data = self.rpc_call(RPCMethod.GET_NOTEBOOK, params, f"/notebook/{notebook_id}")
        
        source_ids = []
        try:
            for s in nb_data[0][1]:
                source_ids.append(s[0][0])
        except (IndexError, TypeError):
            pass
        return source_ids

    def rpc_call(self, method: RPCMethod, params: list, source_path: str = "/"):
        """Make a synchronous RPC call."""
        url = f"{BATCHEXECUTE_URL}?rpcids={method.value}&source-path={source_path}&f.sid={self.session_id}&rt=c"
        
        rpc_req = encode_rpc_request(method, params)
        body = build_request_body(rpc_req, self.csrf_token)
        
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
        res = self.session.post(url, data=body, headers=headers)
        res.raise_for_status()
        
        return decode_response(res.text, method.value)