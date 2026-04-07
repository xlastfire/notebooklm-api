# exceptions.py

class NotebookLMError(Exception): 
    pass

class NetworkError(NotebookLMError):
    def __init__(self, message, method_id=None, original_error=None):
        super().__init__(message)
        self.method_id = method_id
        self.original_error = original_error

class RPCError(NotebookLMError):
    def __init__(self, message, method_id=None, raw_response=None, rpc_code=None, found_ids=None):
        super().__init__(message)
        self.method_id = method_id
        self.raw_response = raw_response
        self.rpc_code = rpc_code
        self.found_ids = found_ids or []

class AuthError(RPCError): pass
class RateLimitError(RPCError): pass
class ServerError(RPCError): pass
class ClientError(RPCError): pass
class RPCTimeoutError(NetworkError): pass