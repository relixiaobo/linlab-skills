class ExecutionState:
    def __init__(self, api):
        self.api = api
        self.runs = {}
        self.sources = {}

    def read_execution(self, run_id):
        run, source = self.api.read_execution(run_id)
        self.runs[run_id] = run
        self.sources[run_id] = source
        return run

    def refresh(self):
        runs, sources = self.api.first_page()
        self.runs.update({run["id"]: run for run in runs})
        self.sources = sources

    def visible_records(self):
        return list(self.runs.values())
