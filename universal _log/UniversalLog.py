from pathlib import Path


class UniversalLog:
    def __init__(self, state, clock_time, log_file="logs.txt"):
        self.bird_type
        self.bird_distance
        self.bird_detect
        self.battery_percent
        self.low
        self.state = state
        self.clock_time = clock_time
        self.log_file = Path(log_file)
        self.write_log()

    def write_log(self):
        """Append the current state and clock time to the log file."""
        if self.state == "IDLE":
            bird_type = "none"
            bird_distance = 0
            bird_detect = False
        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(f"{self.clock_time} - {self.state}\n")
