class ProcessManagementError(Exception):
    pass


class UnknownFunctionError(ProcessManagementError):
    pass


class InjectionError(ProcessManagementError):
    pass


class MaxTasksError(ProcessManagementError):
    pass
