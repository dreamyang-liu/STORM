// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../virtualPersona/IAgentNft.sol";

contract MockAgentNftMinimal {
    mapping(uint256 => IAgentNft.VirtualInfo) private _virtualInfos;

    function setVirtualInfo(
        uint256 virtualId,
        address dao,
        address token,
        address founder,
        address tba,
        uint8[] calldata coreTypes
    ) external {
        _virtualInfos[virtualId] = IAgentNft.VirtualInfo({
            dao: dao,
            token: token,
            founder: founder,
            tba: tba,
            coreTypes: coreTypes
        });
    }

    function virtualInfo(uint256 virtualId) external view returns (IAgentNft.VirtualInfo memory) {
        return _virtualInfos[virtualId];
    }
}
