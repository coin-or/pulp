//! I/O functions for writing LP and MPS files, and reading MPS files.
//! These operate directly on ModelCore data for performance.

use std::collections::HashMap;
use std::io::Write;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::format;
use crate::model::Model;
use crate::types::{Category, ObjSense};
use crate::variable::Variable;

// ── writeLP ──

/// Write an LP file from the Model.
#[pyfunction]
#[pyo3(signature = (model, filename, mip, max_length, obj_name, dummy_var_name, sos_lines))]
pub fn write_lp(
    model: &Model,
    filename: &str,
    mip: bool,
    max_length: usize,
    obj_name: &str,
    dummy_var_name: &str,
    sos_lines: &str,
) -> PyResult<Vec<Variable>> {
    let core = model.core.borrow();

    check_duplicate_vars_core(&core)?;
    check_length_vars_core(&core, max_length)?;

    let mut f = std::fs::File::create(filename)
        .map_err(|e| PyRuntimeError::new_err(format!("Cannot create file: {}", e)))?;

    // Header
    writeln!(f, "\\* {} *\\", core.name)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    let sense_str = if core.sense == ObjSense::Minimize {
        "Minimize"
    } else {
        "Maximize"
    };
    writeln!(f, "{}", sense_str).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    // Objective
    let obj_expr = core
        .objective
        .as_ref()
        .ok_or_else(|| PyValueError::new_err("No objective set"))?;
    let sorted = format::sorted_pairs_from_coeffs(&obj_expr.terms, &core);
    let obj_str = format::cplex_lp_affine_expression(&sorted, obj_expr.constant, obj_name, false);
    write!(f, "{}", obj_str).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    // Subject To
    writeln!(f, "Subject To").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    let mut constr_indices: Vec<usize> = (0..core.constraints.len()).collect();
    constr_indices.sort_by(|a, b| core.constraints[*a].name.cmp(&core.constraints[*b].name));

    let mut dummy_written = false;
    for &ci in &constr_indices {
        let cd = &core.constraints[ci];
        if cd.coeffs.is_empty() {
            if !dummy_written && !dummy_var_name.is_empty() {
                writeln!(f, "_dummy: 1 {} = 0", dummy_var_name)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
                dummy_written = true;
            }
            let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
            writeln!(
                f,
                "{}: 1 {} {} {}",
                cd.name,
                dummy_var_name,
                cd.sense.lp_symbol(),
                format::fmt_g12(rhs)
            )
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            continue;
        }
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
        let s = format::cplex_lp_constraint(&sorted, cd.sense, rhs, &cd.name, false);
        write!(f, "{}", s).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }

    // Bounds
    let vars: Vec<usize> = (0..core.vars.len()).collect();
    let mut bounds_vars: Vec<usize> = Vec::new();
    for &vi in &vars {
        let vd = &core.vars[vi];
        if mip {
            let is_pos_cont =
                vd.lb == 0.0 && vd.ub == f64::INFINITY && vd.category == Category::Continuous;
            let is_bin = vd.is_binary();
            if !is_pos_cont && !is_bin {
                bounds_vars.push(vi);
            }
        } else if !(vd.lb == 0.0 && vd.ub == f64::INFINITY) {
            bounds_vars.push(vi);
        }
    }
    if !bounds_vars.is_empty() {
        writeln!(f, "Bounds").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        for &vi in &bounds_vars {
            let s = format::cplex_lp_variable(&core.vars[vi]);
            writeln!(f, " {}", s).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        }
    }

    // Generals (integer non-binary)
    if mip {
        let generals: Vec<&str> = vars
            .iter()
            .filter(|&&vi| {
                let vd = &core.vars[vi];
                vd.category == Category::Integer && !vd.is_binary()
            })
            .map(|&vi| core.vars[vi].name.as_str())
            .collect();
        if !generals.is_empty() {
            writeln!(f, "Generals").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            for name in generals {
                writeln!(f, "{}", name)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            }
        }

        let binaries: Vec<&str> = vars
            .iter()
            .filter(|&&vi| core.vars[vi].is_binary())
            .map(|&vi| core.vars[vi].name.as_str())
            .collect();
        if !binaries.is_empty() {
            writeln!(f, "Binaries").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            for name in binaries {
                writeln!(f, "{}", name)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            }
        }
    }

    // SOS (pre-formatted from Python)
    if !sos_lines.is_empty() {
        write!(f, "{}", sos_lines).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }

    writeln!(f, "End").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    drop(core);
    let weak = std::rc::Rc::downgrade(&model.core);
    let result: Vec<Variable> = (0..model.core.borrow().vars.len())
        .map(|id| Variable {
            id,
            model: weak.clone(),
        })
        .collect();
    Ok(result)
}

// ── writeMPS ──

/// Write an MPS file from the Model.
#[pyfunction]
#[pyo3(signature = (model, filename, mps_sense, mip, with_objsense, obj_name, obj_terms, model_name))]
pub fn write_mps(
    model: &Model,
    filename: &str,
    mps_sense: i32,
    mip: bool,
    with_objsense: bool,
    obj_name: &str,
    obj_terms: Vec<(usize, f64)>,
    model_name: &str,
) -> PyResult<Vec<Variable>> {
    let core = model.core.borrow();

    let sense_label = if mps_sense == -1 {
        "Maximize"
    } else {
        "Minimize"
    };
    let sense_mps = if mps_sense == -1 { "MAX" } else { "MIN" };

    let mut obj_map: HashMap<usize, f64> = HashMap::new();
    for (vid, coeff) in &obj_terms {
        obj_map.insert(*vid, *coeff);
    }

    let mut f = std::fs::File::create(filename)
        .map_err(|e| PyRuntimeError::new_err(format!("Cannot create file: {}", e)))?;

    // Header
    if with_objsense {
        writeln!(f, "OBJSENSE").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        writeln!(f, " {}", sense_mps).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    } else {
        writeln!(f, "*SENSE:{}", sense_label)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }
    writeln!(f, "NAME          {}", model_name)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    // ROWS
    writeln!(f, "ROWS").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    writeln!(f, " N  {}", obj_name).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    for cd in &core.constraints {
        writeln!(f, " {}  {}", cd.sense.mps_code(), cd.name)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }

    // COLUMNS
    let mut coefs: Vec<Vec<(usize, f64)>> = vec![Vec::new(); core.vars.len()];
    for (ci, cd) in core.constraints.iter().enumerate() {
        for (&vid, &coeff) in &cd.coeffs {
            coefs[vid].push((ci, coeff));
        }
    }

    writeln!(f, "COLUMNS").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    for (vi, vd) in core.vars.iter().enumerate() {
        let cat = vd.category;
        if mip && (cat == Category::Integer || cat == Category::Binary) {
            writeln!(
                f,
                "    MARK      'MARKER'                 'INTORG'"
            )
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        }
        for &(ci, coeff) in &coefs[vi] {
            writeln!(
                f,
                "    {:<8}  {:<8}  {}",
                vd.name,
                core.constraints[ci].name,
                format::mps_float(coeff)
            )
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        }
        if let Some(&obj_coeff) = obj_map.get(&vi) {
            writeln!(
                f,
                "    {:<8}  {:<8}  {}",
                vd.name,
                obj_name,
                format::mps_float(obj_coeff)
            )
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        }
        if mip && (cat == Category::Integer || cat == Category::Binary) {
            writeln!(
                f,
                "    MARK      'MARKER'                 'INTEND'"
            )
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        }
    }

    // RHS
    writeln!(f, "RHS").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    for cd in &core.constraints {
        let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
        writeln!(
            f,
            "    RHS       {:<8}  {}",
            cd.name,
            format::mps_float(rhs)
        )
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }

    // BOUNDS
    writeln!(f, "BOUNDS").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    for vd in &core.vars {
        let lb = if vd.lb.is_finite() {
            Some(vd.lb)
        } else {
            None
        };
        let ub = if vd.ub.is_finite() {
            Some(vd.ub)
        } else {
            None
        };
        let lines = format::mps_bound_lines(&vd.name, lb, ub, vd.category, mip);
        for line in lines {
            write!(f, "{}", line).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        }
    }

    writeln!(f, "ENDATA").map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    drop(core);
    let weak = std::rc::Rc::downgrade(&model.core);
    let result: Vec<Variable> = (0..model.core.borrow().vars.len())
        .map(|id| Variable {
            id,
            model: weak.clone(),
        })
        .collect();
    Ok(result)
}

// ── readMPS ──

/// Parse an MPS file and return a Python dict matching the MPS dataclass shape.
#[pyfunction]
#[pyo3(signature = (path, sense, drop_cons_names=false))]
pub fn read_mps(
    py: Python<'_>,
    path: &str,
    sense: i32,
    drop_cons_names: bool,
) -> PyResult<PyObject> {
    let content = std::fs::read_to_string(path)
        .map_err(|e| PyRuntimeError::new_err(format!("Cannot read file: {}", e)))?;

    let mut mode = String::new();
    let mut name = String::new();
    let mut obj_name = String::new();
    let mut constraints: indexmap::IndexMap<String, MpsConstraintData> = indexmap::IndexMap::new();
    let mut variables: indexmap::IndexMap<String, MpsVarData> = indexmap::IndexMap::new();
    let mut obj_coeffs: Vec<(String, f64)> = Vec::new();
    let mut integral_marker = false;
    let mut rhs_names: Vec<String> = Vec::new();
    let mut bnd_names: Vec<String> = Vec::new();

    for raw_line in content.lines() {
        let tokens: Vec<&str> = raw_line
            .split_whitespace()
            .filter(|s| !s.is_empty())
            .collect();
        if tokens.is_empty() {
            continue;
        }
        if tokens[0] == "ENDATA" {
            break;
        }
        if tokens[0] == "*" {
            continue;
        }
        if tokens[0] == "NAME" {
            name = if tokens.len() > 1 {
                tokens[1].to_string()
            } else {
                String::new()
            };
            continue;
        }

        if tokens[0] == "ROWS" || tokens[0] == "COLUMNS" {
            mode = tokens[0].to_string();
        } else if tokens[0] == "RHS" && tokens.len() <= 2 {
            if tokens.len() > 1 {
                rhs_names.push(tokens[1].to_string());
                mode = "RHS_NAME".to_string();
            } else {
                mode = "RHS_NO_NAME".to_string();
            }
        } else if tokens[0] == "BOUNDS" && tokens.len() <= 2 {
            if tokens.len() > 1 {
                bnd_names.push(tokens[1].to_string());
                mode = "BOUNDS_NAME".to_string();
            } else {
                mode = "BOUNDS_NO_NAME".to_string();
            }
        } else if mode == "ROWS" {
            let row_type = tokens[0];
            let row_name = tokens[1];
            if row_type == "N" {
                obj_name = row_name.to_string();
            } else {
                let sense_val = match row_type {
                    "L" => -1,
                    "E" => 0,
                    "G" => 1,
                    _ => {
                        return Err(PyRuntimeError::new_err(format!(
                            "Unknown row type: {}",
                            row_type
                        )))
                    }
                };
                constraints.insert(
                    row_name.to_string(),
                    MpsConstraintData {
                        name: row_name.to_string(),
                        sense: sense_val,
                        coefficients: Vec::new(),
                        pi: None,
                        constant: 0.0,
                    },
                );
            }
        } else if mode == "COLUMNS" {
            let var_name = tokens[0];
            if tokens.len() > 1 && tokens[1] == "'MARKER'" {
                if tokens.len() > 2 {
                    if tokens[2] == "'INTORG'" {
                        integral_marker = true;
                    } else if tokens[2] == "'INTEND'" {
                        integral_marker = false;
                    }
                }
                continue;
            }
            if !variables.contains_key(var_name) {
                variables.insert(
                    var_name.to_string(),
                    MpsVarData {
                        name: var_name.to_string(),
                        cat: if integral_marker {
                            "Integer"
                        } else {
                            "Continuous"
                        },
                        low_bound: Some(0.0),
                        up_bound: None,
                        var_value: None,
                        dj: None,
                    },
                );
            }
            let mut j = 1;
            while j < tokens.len() - 1 {
                let constr_name = tokens[j];
                let coeff: f64 = tokens[j + 1]
                    .parse()
                    .map_err(|e| PyRuntimeError::new_err(format!("Parse error: {}", e)))?;
                if constr_name == obj_name {
                    obj_coeffs.push((var_name.to_string(), coeff));
                } else if let Some(cd) = constraints.get_mut(constr_name) {
                    cd.coefficients.push((var_name.to_string(), coeff));
                }
                j += 2;
            }
        } else if mode == "RHS_NAME" {
            if tokens[0] != rhs_names.last().unwrap_or(&String::new()).as_str() {
                return Err(PyRuntimeError::new_err(
                    "Other RHS name was given even though name was set after RHS tag.",
                ));
            }
            set_rhs(&tokens, &mut constraints)?;
        } else if mode == "RHS_NO_NAME" {
            set_rhs(&tokens, &mut constraints)?;
            let rn = tokens[0].to_string();
            if !rhs_names.contains(&rn) {
                rhs_names.push(rn);
            }
        } else if mode == "BOUNDS_NAME" {
            if tokens.len() > 1
                && tokens[1] != bnd_names.last().unwrap_or(&String::new()).as_str()
            {
                return Err(PyRuntimeError::new_err(
                    "Other BOUNDS name was given even though name was set after BOUNDS tag.",
                ));
            }
            set_bounds(&tokens, &mut variables)?;
        } else if mode == "BOUNDS_NO_NAME" {
            set_bounds(&tokens, &mut variables)?;
            if tokens.len() > 1 {
                let bn = tokens[1].to_string();
                if !bnd_names.contains(&bn) {
                    bnd_names.push(bn);
                }
            }
        }
    }

    // Build Python dict matching MPS dataclass shape
    let result = PyDict::new(py);

    let params = PyDict::new(py);
    params.set_item("name", &name)?;
    params.set_item("sense", sense)?;
    params.set_item("status", 0)?;
    params.set_item("sol_status", 0)?;
    result.set_item("parameters", params)?;

    let obj_dict = PyDict::new(py);
    if drop_cons_names {
        obj_dict.set_item("name", py.None())?;
    } else {
        obj_dict.set_item("name", &obj_name)?;
    }
    let obj_coeff_list = PyList::empty(py);
    for (vname, coeff) in &obj_coeffs {
        let c = PyDict::new(py);
        c.set_item("name", vname)?;
        c.set_item("value", *coeff)?;
        obj_coeff_list.append(c)?;
    }
    obj_dict.set_item("coefficients", obj_coeff_list)?;
    result.set_item("objective", obj_dict)?;

    let var_list = PyList::empty(py);
    for vd in variables.values() {
        let v = PyDict::new(py);
        v.set_item("name", &vd.name)?;
        v.set_item("cat", vd.cat)?;
        v.set_item("lowBound", vd.low_bound)?;
        v.set_item("upBound", vd.up_bound)?;
        v.set_item("varValue", vd.var_value)?;
        v.set_item("dj", vd.dj)?;
        var_list.append(v)?;
    }
    result.set_item("variables", var_list)?;

    let constr_list = PyList::empty(py);
    for cd in constraints.values() {
        let c = PyDict::new(py);
        if drop_cons_names {
            c.set_item("name", py.None())?;
        } else {
            c.set_item("name", &cd.name)?;
        }
        c.set_item("sense", cd.sense)?;
        c.set_item("pi", cd.pi)?;
        c.set_item("constant", cd.constant)?;
        let coeff_list = PyList::empty(py);
        for (vname, coeff) in &cd.coefficients {
            let cc = PyDict::new(py);
            cc.set_item("name", vname)?;
            cc.set_item("value", *coeff)?;
            coeff_list.append(cc)?;
        }
        c.set_item("coefficients", coeff_list)?;
        constr_list.append(c)?;
    }
    result.set_item("constraints", constr_list)?;

    result.set_item("sos1", PyList::empty(py))?;
    result.set_item("sos2", PyList::empty(py))?;

    Ok(result.into())
}

// ── Internal helpers (MPS parsing only) ──

struct MpsConstraintData {
    name: String,
    sense: i32,
    coefficients: Vec<(String, f64)>,
    pi: Option<f64>,
    constant: f64,
}

struct MpsVarData {
    name: String,
    cat: &'static str,
    low_bound: Option<f64>,
    up_bound: Option<f64>,
    var_value: Option<f64>,
    dj: Option<f64>,
}

fn set_rhs(
    tokens: &[&str],
    constraints: &mut indexmap::IndexMap<String, MpsConstraintData>,
) -> PyResult<()> {
    if tokens.len() >= 3 {
        if let Some(cd) = constraints.get_mut(tokens[1]) {
            let val: f64 = tokens[2]
                .parse()
                .map_err(|e| PyRuntimeError::new_err(format!("Parse error: {}", e)))?;
            cd.constant = -val;
        }
    }
    if tokens.len() >= 5 {
        if let Some(cd) = constraints.get_mut(tokens[3]) {
            let val: f64 = tokens[4]
                .parse()
                .map_err(|e| PyRuntimeError::new_err(format!("Parse error: {}", e)))?;
            cd.constant = -val;
        }
    }
    Ok(())
}

fn set_bounds(
    tokens: &[&str],
    variables: &mut indexmap::IndexMap<String, MpsVarData>,
) -> PyResult<()> {
    let bound = tokens[0];
    let var_name = tokens[2];
    if let Some(vd) = variables.get_mut(var_name) {
        match bound {
            "FR" => {
                vd.low_bound = None;
                vd.up_bound = None;
            }
            "BV" => {
                vd.low_bound = Some(0.0);
                vd.up_bound = Some(1.0);
            }
            "PL" => {
                vd.low_bound = Some(0.0);
                vd.up_bound = None;
            }
            "MI" => {
                vd.low_bound = None;
                vd.up_bound = Some(0.0);
            }
            "LO" | "UP" | "FX" => {
                if tokens.len() < 4 {
                    return Err(PyRuntimeError::new_err(format!(
                        "Missing value for bound type {}",
                        bound
                    )));
                }
                let val: f64 = tokens[3]
                    .parse()
                    .map_err(|e| PyRuntimeError::new_err(format!("Parse error: {}", e)))?;
                match bound {
                    "LO" => vd.low_bound = Some(val),
                    "UP" => vd.up_bound = Some(val),
                    "FX" => {
                        vd.low_bound = Some(val);
                        vd.up_bound = Some(val);
                    }
                    _ => unreachable!(),
                }
            }
            _ => {
                return Err(PyRuntimeError::new_err(format!(
                    "Unknown bound type: {}",
                    bound
                )));
            }
        }
    }
    Ok(())
}

fn check_duplicate_vars_core(
    core: &std::cell::Ref<'_, crate::types::ModelCore>,
) -> PyResult<()> {
    let mut seen: HashMap<&str, usize> = HashMap::new();
    for vd in &core.vars {
        *seen.entry(&vd.name).or_insert(0) += 1;
    }
    let repeated: Vec<(&str, usize)> = seen.into_iter().filter(|(_, c)| *c >= 2).collect();
    if !repeated.is_empty() {
        let msg: Vec<String> = repeated
            .iter()
            .map(|(n, c)| format!("('{}', {})", n, c))
            .collect();
        return Err(PyRuntimeError::new_err(format!(
            "Repeated variable names: {{{}}}",
            msg.join(", ")
        )));
    }
    Ok(())
}

fn check_length_vars_core(
    core: &std::cell::Ref<'_, crate::types::ModelCore>,
    max_length: usize,
) -> PyResult<()> {
    let long: Vec<&str> = core
        .vars
        .iter()
        .filter(|v| v.name.len() > max_length)
        .map(|v| v.name.as_str())
        .collect();
    if !long.is_empty() {
        return Err(PyRuntimeError::new_err(format!(
            "Variable names too long for Lp format: {:?}",
            long
        )));
    }
    Ok(())
}
