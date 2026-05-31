#![doc = include_str!("../README.md")]
#![cfg_attr(docsrs, feature(doc_cfg, doc_auto_cfg))]

mod cli;
mod commands;

fn main() {
    use clap::Parser;

    ploit_utils::sigsegv_handler::install();
    ploit_utils::backtrace::enable();

    if let Err(err) = cli::Cli::parse().run() {
        eprintln!("Error: {err:?}");
        std::process::exit(1);
    }
}
