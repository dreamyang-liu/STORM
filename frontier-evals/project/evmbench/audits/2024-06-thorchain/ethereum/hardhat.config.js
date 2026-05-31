require("@openzeppelin/hardhat-upgrades");
require("@nomiclabs/hardhat-waffle");
require("@nomiclabs/hardhat-truffle5");

task("accounts", "Prints the list of accounts", async () => {
  const accounts = await ethers.getSigners();

  for (const account of accounts) {
    console.log(await account.getAddress());
  }
});

module.exports = {
  solidity: {
    compilers: [
      {
        version: "0.4.17",
      },
      {
        version: "0.7.6",
      },
      {
        version: "0.8.22",
        settings: {
          optimizer: {
            enabled: true,
            runs: 2000,
            details: {
              yul: true,
            },
          },
        },
      },
    ],
  },
  mocha: {
    reporter: "json",
    reporterOptions: {
      output: "test-results.json"
    }
  }
};