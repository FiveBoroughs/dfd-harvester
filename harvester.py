import json
from brownie import accounts, Contract, network

network.connect('geth')
if not (network.is_connected()):
    raise Exception('Network connection failed')
print('Network {}, is active'.format(network.show_active()))

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
INFINITE_UNLOCK = pow(2, 256)-1
DFD_THRESHOLD = 50
SLIPPAGE_PERC = 3
ONEINCH_BASE_URL = "https://api.1inch.exchange/v1.1/swap?fromTokenAddress={0}&toTokenAddress={1}&amount={2}&fromAddress={3}&slippage={SLIPPAGE_PERC}&disableEstimate=true"


def getContract(addy, shortName=None, abiJsonPath=None):
    if(abiJsonPath):
        ctract = Contract.from_abi(shortName, addy, json.loads(
            open(abiJsonPath, "r").read()))
        return ctract
    try:
        ctract = Contract(addy)
        if(shortName):
            ctract.set_alias(shortName)
        return ctract
    except:
        try:
            ctract = Contract.from_explorer(addy)
            if(shortName):
                ctract.set_alias(shortName)
            return ctract
        except:
            raise Exception(
                "Unknown and unable to fetch contract {} from Etherscan, you have to make an interface".format(addy))


token_DFD = getContract('0x20c36f062a31865bed8a5b1e512d9a1a20aa333a', 'DFD')
token_DUSD = getContract('0x5bc25f649fc4e26069ddf4cf4010f9f706c23831', 'DUSD')
token_WETH = getContract(
    '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', 'WETH', 'interfaces/weth.json')


dfd_ilmo_rew_pool = getContract('0xf068236ecad5fabb9883bbb26a6445d6c7c9a924')
dfd_prefarm_pool = getContract(
    '0x7ef30ce82F5A6D0366A3851C4B410ff54A07EADD', 'TokenVesting', 'interfaces/TokenVesting.json')
balancer_dfddusd_pool = getContract(
    '0xd8e9690eff99e21a2de25e0b148ffaf47f47c972')
oneSplit = getContract('0x50FDA034C0Ce7a8f7EFDAebDA7Aa7cA21CC1267e',
                       'OneSplitAudit', 'interfaces/OneSplitAudit.json')

if (len(accounts) < 1):
    raise Exception("No accounts found")

for acct in accounts:
    print('Account {}'.format(acct))

    # Check and claim ILMO rewards
    ilmo_rewards_balance = dfd_ilmo_rew_pool.withdrawAble(
        acct)*0.58 + dfd_ilmo_rew_pool.earned(acct)
    print('Ilmo balance', ilmo_rewards_balance / pow(10, token_DFD.decimals()))
    if(ilmo_rewards_balance > DFD_THRESHOLD):
        print('claiming ilmo')
        tx_dfd_ILMO_claim = dfd_ilmo_rew_pool.exit({'from': acct})

    # Check Pre Farming DFD rewards
    dfd_claimable_balance = dfd_prefarm_pool.claimable(acct)
    print('Prefarm balance', dfd_claimable_balance /
          pow(10, token_DFD.decimals()))
    if(dfd_claimable_balance > DFD_THRESHOLD * pow(10, token_DFD.decimals())):
        print('claiming prefarm')
        tx_dfd_prefarm_claim = dfd_prefarm_pool.claim({'from': acct})

    # Check balancer BPT balance
    bpt_balance = balancer_dfddusd_pool.balanceOf(acct)
    print('Bpt balance', bpt_balance / pow(10, balancer_dfddusd_pool.decimals()))
    if (bpt_balance*0.58 > DFD_THRESHOLD * pow(10, token_DFD.decimals())):
        print('Exiting prefarm')
        tx_balancer_exit = balancer_dfddusd_pool.exitPool(
            bpt_balance, [0, 0], {'from': acct})

    # 1inch DFD Allowance
    oneInch_dfd_allowance = token_DFD.allowance(acct, oneSplit)
    acct_dfd_balance = token_DFD.balanceOf(acct)
    if (acct_dfd_balance > DFD_THRESHOLD):
        if (oneInch_dfd_allowance < acct_dfd_balance):
            print('increasing 1inch allowance, currently ', oneInch_dfd_allowance)

            tx_dfd_1inch_unlock = token_DFD.approve(
                oneSplit, INFINITE_UNLOCK, {'from': acct})

        # Quote price DFD DUSD
        quote = oneSplit.getExpectedReturn(
            token_DFD, token_DUSD, acct_dfd_balance, 1, 0)
        quoteAmount = quote[0]
        quoteDistrib = quote[1]
        print('Obtained Quote price ', quoteAmount /
              pow(10, token_DUSD.decimals()), 'DUSD, performing swap')

        # Swap DFD for DUSD
        oneSplit.swap(token_DFD, token_DUSD, acct_dfd_balance,
                      quoteAmount*(1-SLIPPAGE_PERC/100), quoteDistrib, 0, {'from': acct})
