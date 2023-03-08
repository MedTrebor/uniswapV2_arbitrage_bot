from typing import TypedDict

TxReceipt = TypedDict(
    "TxReceipt",
    {
        "blockHash": str,
        "blockNumber": str,
        "contractAddress": str | None,
        "cumulativeGasUsed": str,
        "effectiveGasPrice": str,
        "from": str,
        "gasUsed": str,
        "logs": list[dict],
        "logsBloom": str,
        "status": str,
        "to": str | None,
        "transactionHash": str,
        "transactionIndex": str,
        "type": str,
    },
)
