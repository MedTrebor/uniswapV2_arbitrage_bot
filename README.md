# [LOCAL BSC](https://github.com/bnb-chain/bsc)

[Documentation](https://docs.bnbchain.org/docs/BSC-fast-node)

<br>

## INSTALL
1. Download BSC from [here](https://github.com/bnb-chain/bsc/releases/download/v1.2.3/geth_windows.exe)
2. Download `genesis.json` and `config.toml` from [here](https://github.com/bnb-chain/bsc/releases/download/v1.2.3/mainnet.zip)
3. Download snapshot from [here](https://github.com/48Club/bsc-snapshots)

<br>

## CONFIG
Change in `config.toml`
```toml
MaxPeers = 600
```

<br>

## RUNNING
1. Prune all trie data
```
./geth snapshot insecure-prune-all --datadir ./node  ./genesis.json
```
2. Start fast node without snapshot verification
```
./geth --tries-verify-mode none --config ./config.toml --datadir ./node  --cache 8000 --rpc.allow-unprotected-txs --txlookuplimit 0
```

<br>

# [QUICKNODE](https://www.quicknode.com/)
Setup 3 seperate **Quicknode** fee accounts [here](https://www.quicknode.com/signup).

<br>

# [PYTHON](https://www.python.org/)
1. Install **Python 3.10** from [here](https://www.python.org/downloads/)
2. Install **Pipenv** using *pip*
```
pip install pipenv
```

<br>

# [BOT](https://github.com/MedTrebor/uniswapV2_arbitrage_bot)
## Download
Download using **SSH** or **HTTPS**.

### SSH
```
git clone --recurse-submodules git@github.com:MedTrebor/uniswapV2_arbitrage_bot.git
```

### HTTP
```
git clone --recurse-submodules https://github.com/MedTrebor/uniswapV2_arbitrage_bot.git
```

<br>

## Dotenv
`.env` file has to be created in root of project

Example:
```
BSC_PK1=0x3d...f1
BURNER_GENERATOR_PK=0x6d...97
QUICKNODE_AUTH1=71...77
BSCSCAN_AUTH=G4J...RH
```

<br>

## Install
```
pipenv install
```

<br>

## Run bot
```
pipenv run main
```

<br>

## Show stats
```
pipenv run stats
```

<br>

## Run any python script
1. Initiate virtual environment
```
pipenv shell
```
2. Run script using **Python**
```
python [file_path]
```

<br>

# IMPORTANT ADDRESSES
## Smart Contracts
| Name | Address |
| --- | --- |
| **ArbRouter** | [`0x5573751B3E18848691896BBEAb396Fc8ac2A579b`](https://bscscan.com/address/0x5573751b3e18848691896bbeab396fc8ac2a579b) |
| **BurnerGenerator** | [`0x6Ad9A356EE572ca0e083a35aF9fb0069C33B7fEb`](https://bscscan.com/address/0x6ad9a356ee572ca0e083a35af9fb0069c33b7feb) |
| **RouterMulticall** | [`0x45306BAFCFA41CF634b4302677f2a3f4474856dc`](https://bscscan.com/address/0x45306BAFCFA41CF634b4302677f2a3f4474856dc)

## Externally Owned Accounts
| Purpose | Address |
| ------ | ------ |
| Calls **ArbRouter** functions | [`0x0000000fEd3a25Eee9d525a5671b5995Fd489fcD`](https://bscscan.com/address/0x0000000fEd3a25Eee9d525a5671b5995Fd489fcD) |
| Calls **BurnerGenerator** to generate burners | [`0x6ad9aEf9E10FC17D2a36769719F18ae17F6a38af`](https://bscscan.com/address/0x6ad9aef9e10fc17d2a36769719f18ae17f6a38af) |

