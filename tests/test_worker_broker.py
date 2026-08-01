import unittest

from src.workers.broker import configure_broker, process_job


class WorkerBrokerTests(unittest.TestCase):
    def test_configured_broker_is_bound_to_actor(self):
        broker = configure_broker("redis://redis.example.test:6379/12")
        self.assertIs(process_job.broker, broker)
        self.assertIs(broker.get_actor("process_job"), process_job)


if __name__ == "__main__":
    unittest.main()
