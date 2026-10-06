"""Isolamento de dados por contexto, propagado explicitamente para workers."""
from contextvars import ContextVar,copy_context

data_directory=ContextVar('edy_data_directory',default=None)


def submit(executor,worker,*args):
    return executor.submit(copy_context().run,worker,*args)
