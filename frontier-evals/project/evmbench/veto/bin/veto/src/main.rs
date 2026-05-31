#![doc = include_str!("../README.md")]
#![cfg_attr(docsrs, feature(doc_cfg, doc_auto_cfg))]
#![cfg_attr(not(test), warn(unused_crate_dependencies))]

use anyhow::Result;

mod cli;
mod telemetry;

#[tokio::main]
async fn main() -> Result<()> {
    telemetry::init();
    cli::run().await
}
