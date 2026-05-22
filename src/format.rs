//! Shared formatting functions used by AffineExpr, Constraint, Variable, and I/O.
//!
//! All functions operate on plain data (`&[(String, f64)]`, `f64`, `Sense`, etc.)
//! so callers only need to resolve VarId -> name once, then delegate here.

use std::io::Write;

use indexmap::IndexMap;

use crate::types::{Category, ModelCore, Sense, VarId, VariableData, LP_CPLEX_LP_LINE_SIZE};

// ── Name resolution ──

/// Resolve VarId -> name from ModelCore, collecting sorted (name, coeff) pairs.
pub fn sorted_pairs_from_coeffs(
    coeffs: &IndexMap<VarId, f64>,
    core: &ModelCore,
) -> Vec<(String, f64)> {
    let mut pairs: Vec<(String, f64)> = coeffs
        .iter()
        .map(|(&vid, &coeff)| {
            let name = core
                .vars
                .get(vid)
                .map(|v| v.name.clone())
                .unwrap_or_default();
            (name, coeff)
        })
        .collect();
    pairs.sort_by(|a, b| a.0.cmp(&b.0));
    pairs
}

// ── Number formatting ──

/// Format a float as Python's `:.12g` (12 significant digits, general notation).
pub fn fmt_g12(v: f64) -> String {
    if v == 0.0 {
        return "0".to_string();
    }
    let abs_v = v.abs();
    let exp = abs_v.log10().floor() as i32;
    if exp < -4 || exp >= 12 {
        let s = format!("{:.12e}", v);
        trim_trailing_zeros_sci(&s)
    } else {
        let decimal_places = (12 - exp - 1).max(0) as usize;
        let s = format!("{:.*}", decimal_places, v);
        trim_trailing_zeros_dec(&s)
    }
}

/// Format a float as Python's `str(float(x))`: always includes a decimal point.
pub fn py_float(v: f64) -> String {
    let s = format!("{}", v);
    if s.contains('.')
        || s.contains('e')
        || s.contains('E')
        || s == "inf"
        || s == "-inf"
        || s == "NaN"
    {
        s
    } else {
        format!("{}.0", s)
    }
}

/// Format a coefficient for human-readable display: show as int when exact.
pub fn format_number(c: f64) -> String {
    let i = c as i64;
    if (c - i as f64).abs() < 1e-15 {
        format!("{}", i)
    } else {
        format!("{}", c)
    }
}

/// Append a float in MPS exponent format (leading space for non-negative, `-` for negative).
pub fn write_mps_float<W: Write>(buf: &mut W, v: f64) -> std::io::Result<()> {
    if v < 0.0 {
        write!(buf, "{:.12e}", v)
    } else {
        write!(buf, " {:.12e}", v)
    }
}

/// Format a float like Python's `% .12e`: leading space for positive, minus for negative.
#[allow(dead_code)]
pub fn mps_float(v: f64) -> String {
    if v < 0.0 {
        format!("{:.12e}", v)
    } else {
        format!(" {:.12e}", v)
    }
}

/// Default value for a variable when no solution exists.
pub fn default_value(lb: f64, ub: f64) -> f64 {
    match (lb.is_finite(), ub.is_finite()) {
        (true, true) => (lb + ub) / 2.0,
        (true, false) => lb,
        (false, true) => ub,
        (false, false) => 0.0,
    }
}

fn trim_trailing_zeros_sci(s: &str) -> String {
    if let Some(e_pos) = s.find('e') {
        let mantissa = &s[..e_pos];
        let exponent = &s[e_pos..];
        if mantissa.contains('.') {
            let trimmed = mantissa.trim_end_matches('0').trim_end_matches('.');
            format!("{}{}", trimmed, exponent)
        } else {
            s.to_string()
        }
    } else {
        s.to_string()
    }
}

fn trim_trailing_zeros_dec(s: &str) -> String {
    if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        s.to_string()
    }
}

// ── CPLEX LP formatting (operates on pre-sorted pairs) ──

/// Build CPLEX LP variable-term lines from sorted (name, coeff) pairs.
/// Returns (completed_lines, current_line_parts) for further appending.
pub fn cplex_variables_only(
    pairs: &[(String, f64)],
    label: &str,
) -> (Vec<String>, Vec<String>) {
    let mut result: Vec<String> = Vec::new();
    let mut line: Vec<String> = vec![format!("{}:", label)];
    let mut not_first = false;
    for (name, val) in pairs {
        let abs_val = val.abs();
        let sign = if *val < 0.0 {
            " -"
        } else if not_first {
            " +"
        } else {
            ""
        };
        not_first = true;
        let term = if abs_val == 1.0 {
            format!("{} {}", sign, name)
        } else {
            format!("{} {} {}", sign, fmt_g12(abs_val), name)
        };
        if line_len(&line) + term.len() > LP_CPLEX_LP_LINE_SIZE {
            result.push(line.concat());
            line = vec![term];
        } else {
            line.push(term);
        }
    }
    (result, line)
}

/// Format a CPLEX LP affine expression string from sorted pairs.
pub fn cplex_lp_affine_expression(
    pairs: &[(String, f64)],
    constant: f64,
    label: &str,
    include_constant: bool,
) -> String {
    let (mut result, line) = cplex_variables_only(pairs, label);
    if include_constant {
        let term = if constant < 0.0 {
            format!(" - {}", fmt_g12(-constant))
        } else if constant > 0.0 {
            format!(" + {}", constant)
        } else {
            " 0".to_string()
        };
        result.push(line.concat() + &term);
    } else {
        result.push(line.concat());
    }
    result.join("\n") + "\n"
}

/// Format a CPLEX LP constraint string from sorted pairs, sense, and RHS.
pub fn cplex_lp_constraint(
    pairs: &[(String, f64)],
    sense: Sense,
    rhs: f64,
    label: &str,
    is_empty: bool,
) -> String {
    let (mut result, mut line) = cplex_variables_only(pairs, label);
    if is_empty {
        line.push("0".to_string());
    }
    let norm_rhs = if rhs == 0.0 { 0.0 } else { rhs };
    let term = format!(" {} {}", sense.lp_symbol(), fmt_g12(norm_rhs));
    if line_len(&line) + term.len() > LP_CPLEX_LP_LINE_SIZE {
        result.push(line.concat());
        line = vec![term];
    } else {
        line.push(term);
    }
    result.push(line.concat());
    result.join("\n") + "\n"
}

// ── Human-readable formatting (operates on pre-sorted pairs) ──

/// Human-readable expression string (Python `_str_expr`).
pub fn str_expr(pairs: &[(String, f64)], constant: f64, include_constant: bool) -> String {
    let mut s = String::new();
    for (name, val) in pairs {
        if *val < 0.0 {
            if s.is_empty() {
                s.push('-');
            } else {
                s.push_str(" - ");
            }
            if *val != -1.0 {
                s.push_str(&format_number(-*val));
                s.push('*');
            }
            s.push_str(name);
        } else if !s.is_empty() {
            s.push_str(" + ");
            if *val != 1.0 {
                s.push_str(&format_number(*val));
                s.push('*');
            }
            s.push_str(name);
        } else {
            if *val != 1.0 {
                s.push_str(&format_number(*val));
                s.push('*');
            }
            s.push_str(name);
        }
    }
    if include_constant {
        if s.is_empty() {
            s = format_number(constant);
        } else if constant < 0.0 {
            s.push_str(" - ");
            s.push_str(&format_number(-constant));
        } else if constant > 0.0 {
            s.push_str(" + ");
            s.push_str(&format_number(constant));
        }
    } else if s.is_empty() {
        s = "0".to_string();
    }
    s
}

/// Human-readable constraint string: "lhs sense rhs".
pub fn str_constraint(
    pairs: &[(String, f64)],
    sense: Sense,
    rhs: f64,
) -> String {
    let lhs = str_expr(pairs, 0.0, false);
    let lhs = if lhs.is_empty() { "0".to_string() } else { lhs };
    format!("{} {} {}", lhs, sense.lp_symbol(), rhs)
}

/// Python `__repr__` string: "coeff*name + ... + constant [sense 0]".
pub fn repr_expr(
    pairs: &[(String, f64)],
    constant: f64,
    sense: Option<Sense>,
) -> String {
    let mut parts: Vec<String> = pairs
        .iter()
        .map(|(name, coeff)| format!("{}*{}", py_float(*coeff), name))
        .collect();
    parts.push(py_float(constant));
    let mut s = parts.join(" + ");
    if let Some(sense) = sense {
        s.push_str(&format!(" {} 0", sense.lp_symbol()));
    }
    s
}

// ── Variable bounds formatting ──

/// CPLEX LP bounds string for a single variable.
pub fn cplex_lp_variable(vd: &VariableData) -> String {
    if vd.is_free() {
        return format!("{} free", vd.name);
    }
    if vd.is_constant() {
        return format!("{} = {}", vd.name, fmt_g12(vd.lb));
    }
    let mut s = if !vd.lb.is_finite() {
        "-inf <= ".to_string()
    } else if vd.lb == 0.0 && vd.category == Category::Continuous {
        String::new()
    } else {
        format!("{} <= ", fmt_g12(vd.lb))
    };
    s.push_str(&vd.name);
    if vd.ub.is_finite() {
        s.push_str(&format!(" <= {}", fmt_g12(vd.ub)));
    }
    s
}

/// Append MPS BOUNDS section lines for a single variable.
pub fn write_mps_bound_lines<W: Write>(
    buf: &mut W,
    name: &str,
    lb: Option<f64>,
    ub: Option<f64>,
    category: Category,
    mip: bool,
) -> std::io::Result<()> {
    if let (Some(low), Some(up)) = (lb, ub) {
        if low == up {
            write!(buf, " FX BND       {:<8}  ", name)?;
            write_mps_float(buf, low)?;
            return writeln!(buf);
        }
    }
    if lb == Some(0.0)
        && ub == Some(1.0)
        && mip
        && (category == Category::Integer || category == Category::Binary)
    {
        return writeln!(buf, " BV BND       {:<8}", name);
    }
    match lb {
        Some(low) => {
            if low != 0.0
                || (mip
                    && (category == Category::Integer || category == Category::Binary)
                    && ub.is_none())
            {
                write!(buf, " LO BND       {:<8}  ", name)?;
                write_mps_float(buf, low)?;
                writeln!(buf)?;
            }
        }
        None => {
            if ub.is_some() {
                writeln!(buf, " MI BND       {:<8}", name)?;
            } else {
                writeln!(buf, " FR BND       {:<8}", name)?;
            }
        }
    }
    if let Some(up) = ub {
        write!(buf, " UP BND       {:<8}  ", name)?;
        write_mps_float(buf, up)?;
        writeln!(buf)?;
    }
    Ok(())
}

/// MPS BOUNDS section lines for a single variable.
#[allow(dead_code)]
pub fn mps_bound_lines(
    name: &str,
    lb: Option<f64>,
    ub: Option<f64>,
    category: Category,
    mip: bool,
) -> Vec<String> {
    let mut buf = Vec::new();
    write_mps_bound_lines(&mut buf, name, lb, ub, category, mip).unwrap();
    let s = String::from_utf8(buf).unwrap();
    s.split_inclusive('\n').map(str::to_string).collect()
}

fn line_len(line: &[String]) -> usize {
    line.iter().map(|t| t.len()).sum()
}

#[cfg(test)]
mod write_mps_format_tests {
    use super::*;
    use crate::types::Category;

    #[test]
    fn write_mps_float_matches_legacy_format() {
        let values = [
            0.0,
            1.0,
            -1.0,
            1e-10,
            -1e-10,
            1e12,
            -1e12,
            1.1,
            4.1,
            7.5,
            9.1,
            1.23456789,
            f64::INFINITY.recip(),
        ];
        for v in values {
            let mut buf = Vec::new();
            write_mps_float(&mut buf, v).unwrap();
            assert_eq!(buf, mps_float(v).into_bytes(), "mismatch for v={v}");
        }
    }

    #[test]
    fn write_mps_bound_lines_matches_legacy() {
        let scenarios: [(&str, Option<f64>, Option<f64>, Category, bool); 10] = [
            ("x", Some(2.0), Some(2.0), Category::Continuous, false),
            ("b", Some(0.0), Some(1.0), Category::Binary, true),
            ("i", Some(0.0), Some(1.0), Category::Integer, true),
            ("y", Some(-1.0), Some(1.0), Category::Continuous, false),
            ("z", Some(0.0), None, Category::Integer, true),
            ("w", None, Some(5.0), Category::Continuous, false),
            ("f", None, None, Category::Continuous, false),
            ("d", Some(0.0), None, Category::Continuous, false),
            ("u", Some(0.0), Some(4.0), Category::Continuous, false),
            ("m", Some(0.0), Some(1.0), Category::Continuous, true),
        ];
        for (name, lb, ub, category, mip) in scenarios {
            let mut buf = Vec::new();
            write_mps_bound_lines(&mut buf, name, lb, ub, category, mip).unwrap();
            let legacy = mps_bound_lines(name, lb, ub, category, mip)
                .concat()
                .into_bytes();
            assert_eq!(
                buf,
                legacy,
                "mismatch for name={name} lb={lb:?} ub={ub:?} category={category:?} mip={mip}"
            );
        }
    }
}
