mod cli;
mod cmux;
mod envelope;
mod fs_state;
mod model;

fn main() {
    if let Err(error) = cli::run(std::env::args().skip(1).collect()) {
        envelope::print_error("cli", "error", &error);
        std::process::exit(1);
    }
}
