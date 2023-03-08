class NetworkError(Exception):
    pass


class GasPriceError(NetworkError):
    pass


class MaxGasParamsError(NetworkError):
    pass
