use serde::Serialize;
use serde_json::json;

pub fn print_ok<T: Serialize>(operation: &str, data: T) {
    let body = json!({
        "schema_version": "1.0",
        "ok": true,
        "operation": operation,
        "data": data,
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&body).expect("serialize envelope")
    );
}

pub fn print_error(operation: &str, code: &str, message: &str) {
    let body = json!({
        "schema_version": "1.0",
        "ok": false,
        "operation": operation,
        "error": {
            "code": code,
            "message": message,
        },
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&body).expect("serialize envelope")
    );
}
