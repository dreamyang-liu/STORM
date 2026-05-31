// SPDX-License-Identifier: BUSL-1.1
pragma solidity ^0.8.0;

import {Ownable2Step} from '@openzeppelin/contracts/access/Ownable2Step.sol';
import {ERC20} from '@openzeppelin/contracts/token/ERC20/ERC20.sol';

import {IeETH} from 'src/yield/etherfi/IeETH.sol';
import {ILiquidityPool} from 'src/yield/etherfi/ILiquidityPool.sol';
import {IWithdrawRequestNFT} from 'src/yield/etherfi/IWithdrawRequestNFT.sol';

import {MockeETH} from './MockeETH.sol';

contract MockEtherfiLiquidityPool is ILiquidityPool, Ownable2Step {
  address public override eETH;
  address public override withdrawRequestNFT;

  constructor(address _eETH, address _withdrawRequestNFT) {
    eETH = _eETH;
    withdrawRequestNFT = _withdrawRequestNFT;
  }

  function deposit() external payable override returns (uint256) {
    require(msg.value > 0, 'msg value is 0');

    MockeETH(payable(eETH)).mint(msg.sender, msg.value);
    return msg.value * 9 / 10;
  }

  function rebase(address to) public payable returns (uint256) {
    require(msg.value > 0, 'msg value is 0');

    MockeETH(payable(eETH)).mint(to, msg.value);
    return msg.value;
  }

  function requestWithdraw(address recipient, uint256 amount) external override returns (uint256) {
    IeETH(payable(eETH)).transferFrom(msg.sender, address(withdrawRequestNFT), amount);

    uint256 requestId = IWithdrawRequestNFT(withdrawRequestNFT).requestWithdraw(
      uint96(amount),
      uint96(amount),
      recipient,
      0
    );
    return requestId;
  }

  function withdraw(address _recipient, uint256 _amount) external override returns (uint256) {
    require(msg.sender == address(withdrawRequestNFT), 'Incorrect Caller');

    MockeETH(payable(eETH)).burn(msg.sender, _amount);

    _sendFund(_recipient, _amount);

    return _amount;
  }

  function transferETH(address to) public onlyOwner {
    (bool success, ) = to.call{value: address(this).balance}('');
    require(success, 'send value failed');
  }

  function setEETH(address _eETH, address _withdrawRequestNFT) public onlyOwner {
    eETH = _eETH;
    withdrawRequestNFT = _withdrawRequestNFT;
  }

  function _sendFund(address _recipient, uint256 _amount) internal {
    uint256 balanace = address(this).balance;
    (bool sent, ) = _recipient.call{value: _amount}('');
    require(sent && address(this).balance == balanace - _amount, 'SendFail');
  }

  receive() external payable {}
}
