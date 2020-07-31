import asyncio
import logging

from ether import calldata, ethrpc

from maintainer import config

from ether.ether_types import Receipt
from ether.transactions import UnsignedEthTx
from typing import Any, cast, Dict, Iterator, List, Optional

logger = logging.getLogger('root.summa_relay.shared_eth')


GWEI = 1000000000
DEFAULT_GAS = 500_000
DEFAULT_GAS_PRICE = 20 * GWEI
MAX_GAS_PRICE = 80 * GWEI

CONNECTION: ethrpc.BaseRPC
NONCE: Iterator[int]  # yields ints, takes no sends
LATEST_PENDING_NONCE = 0

def _nonce(i: int) -> Iterator[int]:
    '''Infinite generator for nonces'''
    index = i
    while 1:
        yield index
        index += 1


async def init() -> None:
    '''Set up a connection to the interwebs'''
    global CONNECTION

    c = config.get()
    network = c['NETWORK']
    project_id = c['PROJECT_ID']
    uri = c['ETHER_URL']
    force_https = project_id != ''

    logger.info(f'contract is {c["CONTRACT"]}')

    CONNECTION = ethrpc.get_client(
        network=network,
        infura_key=project_id,
        uri=uri,
        logger=logger.getChild('ethrpc'),
        force_https=force_https)

    await CONNECTION.open()

    if c['PRIVKEY'] is None and c['GETH_UNLOCK'] is None:
        logger.warn(
            'No ethereum privkey found in env config. Txns will error')
    else:
        global NONCE
        global LATEST_PENDING_NONCE
        address = cast(str, c['ETH_ADDRESS'])
        # Get the already-mined count.
        mined_tx_count = int(await CONNECTION._RPC(
            method='eth_getTransactionCount',
            params=[address, 'latest']), 16) - 1
        logger.info(f'mined tx count is {mined_tx_count}')

        LATEST_PENDING_NONCE = await CONNECTION.get_nonce(address) - 1
        logger.info(f'latest pending nonce is {LATEST_PENDING_NONCE}')

        # Replace all pending txes by starting the nonce at the mined count.
        # Note that we could crash if the next tx we send finds the first
        # unconfirmed nonce having already been mined---this is fine, the
        # process can be restarted and will read the latest pending and mined
        # state at that time.
        #
        # If all pending nonces are already complete, make sure to start 1
        # ahead.
        next_nonce = mined_tx_count + 1
        NONCE = _nonce(next_nonce)
        logger.info(f'next nonce is {next_nonce}')

async def close_connection() -> None:
    try:
        global CONNECTION
        await CONNECTION.close()
    except NameError:
        pass


async def sign_and_broadcast(
        tx: UnsignedEthTx,
        ignore_result: bool = False,
        ticks: int = 0) -> None:
    '''Sign an ethereum transaction and broadcast it to the network'''
    c = config.get()
    privkey = c['PRIVKEY']
    address = c['ETH_ADDRESS']
    unlock_code = c['GETH_UNLOCK']

    if privkey is None and unlock_code is None:
        raise RuntimeError('Attempted to sign tx without access to key')

    logger.info(f'dispatching transaction at nonce {tx.nonce} with gas price {tx.gasPrice}')
    try:
        if privkey is None:
            logger.debug('signing with ether node')
            await CONNECTION._RPC(
                'personal_unlockAccount',
                [address, unlock_code])
            tx_id = await CONNECTION.send_transaction(cast(str, address), tx)
        else:
            logger.debug('signing with local key')
            signed = tx.sign(cast(bytes, privkey))
            serialized = signed.serialize_hex()
            tx_id = await CONNECTION.broadcast(serialized)
    except RuntimeError as err:
        if type(err.args[0]) is dict and 'known transaction: ' in dict(err.args[0])['message']:
            tx_id = dict(err.args[0])[19:]
        elif 'transaction underpriced' in err.args[0] or 'already known' in err.args[0]:
            logger.warn(
                f'Got an error {err} submitting nonce {tx.nonce} at gas price ' +
                f'{tx.gasPrice}; boosting gas.'
            )
            # We're trying to submit a transaction that's already been
            # submitted; start a retry loop so we can climb to a higher
            # gas level if needed.
            asyncio.ensure_future(_track_tx_result(tx, ""))
            return
        elif 'nonce too low' in err.args[0] and ticks > 0:
            logger.warn(
                f'Got an error {err} submitting nonce {tx.nonce} at gas price ' +
                f'{tx.gasPrice}; assuming a lower-priced version cleared and ' +
                f'continuing normally.'
            )
        else:
            raise err # re-raise

    logger.info(f'dispatched transaction {tx_id} at nonce {tx.nonce} with gas price {tx.gasPrice}')
    if not ignore_result:
        asyncio.ensure_future(_track_tx_result(tx, tx_id, ticks))


def make_call_tx(
        contract: str,
        abi: List[Dict[str, Any]],
        method: str,
        args: List[Any],
        nonce: int,
        value: int = 0,
        gas: int = DEFAULT_GAS,
        gas_price: int = -1) -> UnsignedEthTx:
    '''
    Sends tokens to a recipient
    Args:
        contract      (str): address of contract being called
        abi          (dict): contract ABI
        method        (str): the name of the method to call
        args         (list): the arguments to the method call
        nonce         (int): the account nonce for the txn
        value         (int): ether in wei
        gas_price     (int): the price of gas in wei or gwei
    Returns:
        (UnsignedEthTx): the unsigned tx object
    '''
    logger.debug(f'making tx call {method} on {contract} '
                 f'with value {value} and {len(args)} args')

    global LATEST_PENDING_NONCE

    # Adjust gas price for current pending txes.
    if gas_price == -1:
        gas_price = _compute_tx_gas_price(nonce, 0)

    if nonce > LATEST_PENDING_NONCE:
        LATEST_PENDING_NONCE = nonce

    gas_price = _adjust_gas_price(gas_price)
    chainId = config.get()['CHAIN_ID']

    data = calldata.call(
        method,
        args,
        abi)

    txn = UnsignedEthTx(
        to=contract,
        value=value,
        gas=gas,
        gasPrice=gas_price,
        nonce=nonce,
        data=data,
        chainId=chainId)

    return txn


def _adjust_gas_price(gas_price: int) -> int:
    '''
    We accept gas price in GWEI or in WEI.
    This adjusts, and ensures we error if it's high.
    Args:
        gas_price (int): the user-provided gas price
    Returns:
        (int): the adjusted price
    '''
    if gas_price < GWEI:
        gas_price = gas_price * GWEI
    if gas_price > 1000 * GWEI:
        logger.error('rejecting high gas price')
        raise ValueError(
            'very high gas price detected: {} gwei'.format(gas_price / GWEI))
    return gas_price

def _compute_tx_gas_price(tx_nonce, tx_ticks):
    '''Compute the proper gas price, adjusting for other pending txes and how
    long this tx has been pending, taking the max gas price into account.'''
    gas_price_factor = max((LATEST_PENDING_NONCE - tx_nonce + 1) * tx_ticks, 0)
    adjusted_gas_price = round((1 + gas_price_factor * 0.2) * DEFAULT_GAS_PRICE)

    return max(min(adjusted_gas_price, MAX_GAS_PRICE), DEFAULT_GAS_PRICE)

async def _track_tx_result(tx: UnsignedEthTx, tx_id: str, ticks: int = 0) -> None:
    '''Keep track of the result of a transaction by polling every 25 seconds'''
    receipt_or_none: Optional[Receipt] = None

    latest_gas_price = tx.gasPrice

    for _ in range(20):
        await asyncio.sleep(30)
        receipt_or_none = None
        if tx_id != "":
            receipt_or_none = await CONNECTION.get_tx_receipt(tx_id)

        if receipt_or_none is not None:
            break
        else:
            ticks += 1
            new_gas_price = _compute_tx_gas_price(tx.nonce, ticks)

            # If the new gas price is higher, resubmit this transaction with a
            # boosted gas price to improve chances of confirmation.
            if new_gas_price > latest_gas_price:
                logger.info(f'resubmitting {tx_id} with gas price {new_gas_price}')
                newTx = UnsignedEthTx(
                    nonce = tx.nonce,
                    gasPrice = new_gas_price,
                    gas = tx.gas,
                    to = tx.to,
                    value = tx.value,
                    data = tx.data,
                    chainId = tx.chainId)

                # Broadcast and set up tracking for the new tx, and stop
                # watching this one.
                await sign_and_broadcast(newTx, False, ticks)
                return

    # This is reachable only when we've hit max gas.
    if receipt_or_none is None:
        raise RuntimeError(f'No receipt after 10 minutes: {tx_id}, nonce: {tx.nonce}, gas price: {tx.gasPrice}')

    receipt = cast(Receipt, receipt_or_none)
    logger.info(f'Receipt for {tx_id} status is {receipt["status"]}')

    if receipt['status'] != '0x1':
        raise RuntimeError(f'Failed tx: {receipt["transactionHash"]}')
