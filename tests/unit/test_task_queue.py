from backend.infra.tasks.inline import InlineTaskQueue


def test_inline_task_queue_runs_synchronously():
    called = {}

    def my_task(x, y):
        called['result'] = x + y

    tq = InlineTaskQueue()
    tq.enqueue(my_task, 2, 3)
    assert called['result'] == 5 