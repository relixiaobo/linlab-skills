class Host:
    def __init__(self, backend, allowed_threads):
        self.backend = backend
        self.allowed_threads = allowed_threads

    async def resolve(self, source):
        if not isinstance(source, dict) or not isinstance(source.get("thread_id"), str):
            raise ValueError("Invalid source")
        thread_id = source["thread_id"]
        if thread_id not in self.allowed_threads:
            raise PermissionError("Source access denied")
        revision = self.backend.revision(thread_id)
        window = await self.backend.read_window(thread_id, source["turn_id"], limit=30)
        if self.backend.revision(thread_id) != revision:
            raise RuntimeError("Source changed during read")
        return window

    async def load_metadata(self, thread_id):
        return await self.backend.read_metadata(thread_id)
