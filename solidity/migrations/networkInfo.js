require('dotenv').config();
const BN = require('bn.js');

const ID_SPACE_SIZE = new BN('2', 10).pow(new BN('32', 10));

const truffleConf = require('../truffle-config');

const bitcoinMain = {
  genesis: '0x00006020dd02d03c03dbc1f41312a6940e89919ce67fbf99a20307000000000000000000260d70e7ae07c80db07fbf29d09ec1a86d4f788e58098189a6f9021236572a7dd99eb15e397a11178294a823',
  height: 629070,
  epochStart: '0x459ec50d4ea62a89da04eb1ef3e352ec740bca50e8a808000000000000000000',
};

const bitcoinTest = {
  genesis: '0x0000c0205d1103efc13e6647977e3d65f253c3e762451e9ca9b920517d000000000000008442a07bcde3292a888277ea6337ba5bbdfa808ae01535846f19d843144c8f60478bb15e7b41011a88be5d36',
  height: 1723030,
  epochStart: '0xe2657f702faa9470815005305c45b4be2271c22ade1348e6fe00000000000000'
};

module.exports = {
  ropsten: {
    network_id: truffleConf.networks.ropsten.network_id,
    bitcoin: bitcoinMain,
    firstID: ID_SPACE_SIZE.muln(truffleConf.networks.ropsten.network_id)
  },
  ropsten_test: {
    network_id: truffleConf.networks.ropsten_test.network_id,
    bitcoin: bitcoinTest,
    firstID: ID_SPACE_SIZE.muln(truffleConf.networks.ropsten_test.network_id + 0x800000)
  },
  kovan: {
    network_id: truffleConf.networks.kovan.network_id,
    bitcoin: bitcoinMain,
    firstID: ID_SPACE_SIZE.muln(truffleConf.networks.kovan.network_id)
  },
  kovan_test: {
    network_id: truffleConf.networks.kovan_test.network_id,
    bitcoin: bitcoinTest,
    firstID: ID_SPACE_SIZE.muln(truffleConf.networks.kovan_test.network_id + 0x800000)
  },
  alfajores: {
    network_id: truffleConf.networks.alfajores_test.network_id,
    bitcoin: bitcoinMain,
    firstID: ID_SPACE_SIZE.muln(truffleConf.networks.alfajores.network_id)
  },
  alfajores_test: {
    network_id: truffleConf.networks.alfajores_test.network_id,
    bitcoin: bitcoinTest,
    firstID: ID_SPACE_SIZE.muln(truffleConf.networks.alfajores_test.network_id + 0x800000)
  },
};
