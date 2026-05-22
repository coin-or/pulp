//! I/O functions for writing LP and MPS files, and reading MPS files.
//! These operate directly on ModelCore data for performance.

use std::collections::HashSet;
use std::io::{BufWriter, Write};
use std::sync::Arc;

use indexmap::IndexMap;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyFloat, PyList, PyString};

use crate::format;
use crate::model::Model;
use crate::types::{lock_model, Category, ModelCore, ObjSense, Sense, SosKind, VarId};
use crate::variable::Variable;

macro_rules! writeln_mps {
    ($f:expr, $fmt:literal $(, $arg:expr)* $(,)?) => {{
        std::io::Write::write_fmt(&mut $f, format_args!(concat!($fmt, "\n") $(, $arg)*))
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }};
}

macro_rules! write_mps {
    ($f:expr, $($arg:tt)*) => {
        std::io::Write::write_fmt(&mut $f, format_args!($($arg)*))
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?
    };
}

// ── writeLP ──

fn format_sos_lp_section(core: &ModelCore) -> String {
    let mut out = String::new();
    for g in &core.sos {
        let header = match g.kind {
            SosKind::Sos1 => "S1::",
            SosKind::Sos2 => "S2::",
        };
        out.push_str(header);
        out.push_str(" \n");
        for &(vid, w) in &g.weights {
            if let Some(vd) = core.vars.get(vid) {
                out.push_str(&format!(" {}: {}\n", vd.name, format::fmt_g12(w)));
            }
        }
    }
    out
}

/// Write an LP file from the Model (only variables used in objective, constraints, or SOS).
#[pyfunction]
#[pyo3(signature = (model, filename, mip, max_length, obj_name, dummy_var_name))]
pub fn write_lp(
    model: &Model,
    filename: &str,
    mip: bool,
    max_length: usize,
    obj_name: &str,
    dummy_var_name: &str,
) -> PyResult<Vec<Variable>> {
    let core = lock_model(&model.core);

    core.check_duplicate_var_names()?;
    core.check_duplicate_constraint_names()?;
    core.check_var_name_lengths(max_length)?;

    let used = core.used_var_ids();
    let used_set: HashSet<VarId> = used.iter().copied().collect();

    let mut f = std::fs::File::create(filename)
        .map_err(|e| PyRuntimeError::new_err(format!("Cannot create file: {}", e)))?;

    // Header
    writeln_mps!(f, "\\* {} *\\", core.name);
    let sense_str = if core.sense == ObjSense::Minimize {
        "Minimize"
    } else {
        "Maximize"
    };
    writeln_mps!(f, "{}", sense_str);

    // Objective (only used variables)
    let obj_expr = core
        .objective
        .as_ref()
        .ok_or_else(|| PyValueError::new_err("No objective set"))?;
    let filtered_terms: IndexMap<VarId, f64> = obj_expr
        .terms
        .iter()
        .filter(|(vid, _)| used_set.contains(vid))
        .map(|(&k, &v)| (k, v))
        .collect();
    let sorted = format::sorted_pairs_from_coeffs(&filtered_terms, &core);
    let obj_str = format::cplex_lp_affine_expression(&sorted, obj_expr.constant, obj_name, false);
    write_mps!(f, "{}", obj_str);

    // Subject To
    writeln_mps!(f, "Subject To");

    let mut constr_indices: Vec<usize> = (0..core.constraints.len()).collect();
    constr_indices.sort_by(|a, b| core.constraints[*a].name.cmp(&core.constraints[*b].name));

    let mut dummy_written = false;
    for &ci in &constr_indices {
        let cd = &core.constraints[ci];
        if cd.coeffs.is_empty() {
            if !dummy_written && !dummy_var_name.is_empty() {
                writeln_mps!(f, "_dummy: 1 {} = 0", dummy_var_name);
                dummy_written = true;
            }
            let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
            writeln_mps!(
                f,
                "{}: 1 {} {} {}",
                cd.name,
                dummy_var_name,
                cd.sense.lp_symbol(),
                format::fmt_g12(rhs)
            );
            continue;
        }
        let filtered: IndexMap<VarId, f64> = cd
            .coeffs
            .iter()
            .filter(|(vid, _)| used_set.contains(vid))
            .map(|(&k, &v)| (k, v))
            .collect();
        let sorted = format::sorted_pairs_from_coeffs(&filtered, &core);
        let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
        let s = format::cplex_lp_constraint(&sorted, cd.sense, rhs, &cd.name, false);
        write_mps!(f, "{}", s);
    }

    // Bounds (used variables only)
    let mut bounds_vars: Vec<usize> = Vec::new();
    for &vi in &used {
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
        writeln_mps!(f, "Bounds");
        for &vi in &bounds_vars {
            let s = format::cplex_lp_variable(&core.vars[vi]);
            writeln_mps!(f, " {}", s);
        }
    }

    // Generals (integer non-binary)
    if mip {
        let generals: Vec<&str> = used
            .iter()
            .filter(|&&vi| {
                let vd = &core.vars[vi];
                vd.category == Category::Integer && !vd.is_binary()
            })
            .map(|&vi| core.vars[vi].name.as_str())
            .collect();
        if !generals.is_empty() {
            writeln_mps!(f, "Generals");
            for name in generals {
                writeln_mps!(f, "{}", name);
            }
        }

        let binaries: Vec<&str> = used
            .iter()
            .filter(|&&vi| core.vars[vi].is_binary())
            .map(|&vi| core.vars[vi].name.as_str())
            .collect();
        if !binaries.is_empty() {
            writeln_mps!(f, "Binaries");
            for name in binaries {
                writeln_mps!(f, "{}", name);
            }
        }
    }

    let sos_block = format_sos_lp_section(&core);
    if !sos_block.is_empty() {
        writeln_mps!(f, "SOS");
        write_mps!(f, "{}", sos_block);
    }

    writeln_mps!(f, "End");

    drop(core);
    let weak = Arc::downgrade(&model.core);
    let result: Vec<Variable> = used
        .into_iter()
        .map(|id| Variable {
            id,
            model: weak.clone(),
        })
        .collect();
    Ok(result)
}

// ── writeMPS ──

const MPS_BUFWRITER_CAPACITY: usize = 1 << 20;

pub(crate) struct MpsWriter<W: Write> {
    out: W,
}

impl<W: Write> MpsWriter<W> {
    fn new(out: W) -> Self {
        Self { out }
    }

    fn write_column_entry(&mut self, vname: &str, row: &str, coeff: f64) -> PyResult<()> {
        self.out
            .write_fmt(format_args!("    {:<8}  {:<8}  ", vname, row))
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        format::write_mps_float(&mut self.out, coeff)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        self.out
            .write_all(b"\n")
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }

    fn finish(mut self) -> PyResult<()> {
        self.out
            .flush()
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

impl<W: Write> Write for MpsWriter<W> {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        self.out.write(buf)
    }

    fn flush(&mut self) -> std::io::Result<()> {
        self.out.flush()
    }
}

impl MpsWriter<BufWriter<std::fs::File>> {
    fn create(path: &str) -> PyResult<Self> {
        let f = std::fs::File::create(path)
            .map_err(|e| PyRuntimeError::new_err(format!("Cannot create file: {}", e)))?;
        Ok(Self::new(BufWriter::with_capacity(
            MPS_BUFWRITER_CAPACITY,
            f,
        )))
    }
}

#[cfg(test)]
impl MpsWriter<Vec<u8>> {
    fn in_memory() -> Self {
        Self::new(Vec::with_capacity(64 * 1024))
    }

    fn into_bytes(self) -> Vec<u8> {
        self.out
    }
}

struct MpsWriteParams<'a> {
    mps_sense: i32,
    mip: bool,
    with_objsense: bool,
    rename: bool,
    model_name: &'a str,
    obj_name: &'a str,
}

fn build_mps_names(
    core: &ModelCore,
    used: &[VarId],
    pulp_names: &[String],
    rename: bool,
    obj_name: &str,
) -> (Vec<String>, Vec<String>, String) {
    let file_obj_name = if rename {
        "OBJ".to_string()
    } else {
        obj_name.to_string()
    };
    let var_names: Vec<String> = if rename {
        (0..used.len()).map(|j| format!("X{:07}", j)).collect()
    } else {
        pulp_names.to_vec()
    };
    let constr_names: Vec<String> = if rename {
        (0..core.constraints.len())
            .map(|i| format!("C{:07}", i))
            .collect()
    } else {
        core.constraints.iter().map(|cd| cd.name.clone()).collect()
    };
    (var_names, constr_names, file_obj_name)
}

fn emit_mps_into<W: Write>(
    w: &mut MpsWriter<W>,
    core: &ModelCore,
    used: &[VarId],
    var_names: &[String],
    constr_names: &[String],
    obj_map: &[Option<f64>],
    params: &MpsWriteParams<'_>,
) -> PyResult<()> {
    let sense_label = if params.mps_sense == -1 {
        "Maximize"
    } else {
        "Minimize"
    };
    let sense_mps = if params.mps_sense == -1 { "MAX" } else { "MIN" };
    let file_obj_name = if params.rename {
        "OBJ"
    } else {
        params.obj_name
    };

    if params.with_objsense {
        writeln_mps!(&mut *w, "OBJSENSE");
        writeln_mps!(&mut *w, " {}", sense_mps);
    } else {
        writeln_mps!(&mut *w, "*SENSE:{}", sense_label);
    }
    writeln_mps!(
        &mut *w,
        "{}          {}",
        MpsSection::Name.as_token(),
        params.model_name
    );

    writeln_mps!(&mut *w, "{}", MpsSection::Rows.as_token());
    writeln_mps!(
        &mut *w,
        " {}  {}",
        MpsRowType::Objective.as_token(),
        file_obj_name
    );
    for (ci, cd) in core.constraints.iter().enumerate() {
        writeln_mps!(
            &mut *w,
            " {}  {}",
            sense_to_mps_row_type(cd.sense).as_token(),
            constr_names[ci]
        );
    }

    let mut coefs: Vec<Vec<(usize, f64)>> = vec![Vec::new(); core.vars.len()];
    for (ci, cd) in core.constraints.iter().enumerate() {
        for (&vid, &coeff) in &cd.coeffs {
            coefs[vid].push((ci, coeff));
        }
    }

    writeln_mps!(&mut *w, "{}", MpsSection::Columns.as_token());
    for (j, &vi) in used.iter().enumerate() {
        let vd = &core.vars[vi];
        let cat = vd.category;
        let vname = &var_names[j];
        if params.mip && (cat == Category::Integer || cat == Category::Binary) {
            writeln_mps!(
                &mut *w,
                "    MARK      {}                 {}",
                MPS_COLUMNS_MARKER,
                MpsMarker::IntOrg.as_token()
            );
        }
        for &(ci, coeff) in &coefs[vi] {
            let constr_name = constr_names[ci].as_str();
            w.write_column_entry(vname, constr_name, coeff)?;
        }
        if let Some(obj_coeff) = obj_map[vi] {
            w.write_column_entry(vname, file_obj_name, obj_coeff)?;
        }
        if params.mip && (cat == Category::Integer || cat == Category::Binary) {
            writeln_mps!(
                &mut *w,
                "    MARK      {}                 {}",
                MPS_COLUMNS_MARKER,
                MpsMarker::IntEnd.as_token()
            );
        }
    }

    writeln_mps!(&mut *w, "{}", MpsSection::Rhs.as_token());
    for (ci, cd) in core.constraints.iter().enumerate() {
        let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
        let constr_name = constr_names[ci].as_str();
        w.out
            .write_fmt(format_args!("    RHS       {:<8}  ", constr_name))
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        format::write_mps_float(&mut w.out, rhs)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        w.out
            .write_all(b"\n")
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }

    writeln_mps!(&mut *w, "{}", MpsSection::Bounds.as_token());
    for (j, &vi) in used.iter().enumerate() {
        let vd = &core.vars[vi];
        let vname = &var_names[j];
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
        format::write_mps_bound_lines(&mut w.out, vname, lb, ub, vd.category, params.mip)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    }

    writeln_mps!(&mut *w, "{}", MpsSection::Endata.as_token());
    Ok(())
}

#[cfg(test)]
pub(crate) fn write_mps_buffer(
    core: &ModelCore,
    mps_sense: i32,
    mip: bool,
    with_objsense: bool,
    rename: bool,
    model_name: &str,
    obj_name: &str,
) -> PyResult<Vec<u8>> {
    core.check_duplicate_var_names()?;
    core.check_duplicate_constraint_names()?;

    let used = core.used_var_ids();
    let pulp_names: Vec<String> = used
        .iter()
        .map(|&vid| core.vars[vid].name.clone())
        .collect();

    let mut obj_map: Vec<Option<f64>> = vec![None; core.vars.len()];
    if let Some(ref expr) = core.objective {
        let sign = if !with_objsense && mps_sense == -1 {
            -1.0
        } else {
            1.0
        };
        for (&vid, &coeff) in &expr.terms {
            obj_map[vid] = Some(coeff * sign);
        }
    }

    let (var_names, constr_names, _file_obj_name) =
        build_mps_names(core, &used, &pulp_names, rename, obj_name);

    let params = MpsWriteParams {
        mps_sense,
        mip,
        with_objsense,
        rename,
        model_name: if rename { "MODEL" } else { model_name },
        obj_name,
    };

    let mut w = MpsWriter::in_memory();
    emit_mps_into(
        &mut w,
        core,
        &used,
        &var_names,
        &constr_names,
        &obj_map,
        &params,
    )?;
    Ok(w.into_bytes())
}

/// Write an MPS file from the Model (only used variable columns).
/// Returns `(variable_names, constraint_names, objective_name, pulp_names_in_column_order)`:
/// `variable_names` are file tokens (`X0000000` when `rename`); `pulp_names_in_column_order`
/// are the original PuLP variable names in the same column order (for solution readback).
#[pyfunction]
#[pyo3(signature = (model, filename, mps_sense, mip, with_objsense, rename, model_name, obj_name))]
pub fn write_mps(
    model: &Model,
    filename: &str,
    mps_sense: i32,
    mip: bool,
    with_objsense: bool,
    rename: bool,
    model_name: &str,
    obj_name: &str,
) -> PyResult<(Vec<String>, Vec<String>, String, Vec<String>)> {
    let core = lock_model(&model.core);
    core.check_duplicate_var_names()?;
    core.check_duplicate_constraint_names()?;

    let used = core.used_var_ids();
    let pulp_names: Vec<String> = used
        .iter()
        .map(|&vid| core.vars[vid].name.clone())
        .collect();

    let mut obj_map: Vec<Option<f64>> = vec![None; core.vars.len()];
    if let Some(ref expr) = core.objective {
        let sign = if !with_objsense && mps_sense == -1 {
            -1.0
        } else {
            1.0
        };
        for (&vid, &coeff) in &expr.terms {
            obj_map[vid] = Some(coeff * sign);
        }
    }

    let (var_names, constr_names, file_obj_name) =
        build_mps_names(&core, &used, &pulp_names, rename, obj_name);

    let params = MpsWriteParams {
        mps_sense,
        mip,
        with_objsense,
        rename,
        model_name: if rename { "MODEL" } else { model_name },
        obj_name,
    };

    let mut w = MpsWriter::create(filename)?;
    emit_mps_into(
        &mut w,
        &core,
        &used,
        &var_names,
        &constr_names,
        &obj_map,
        &params,
    )?;
    w.finish()?;

    drop(core);

    Ok((
        var_names,
        constr_names,
        file_obj_name,
        pulp_names,
    ))
}

// ── readMPS ──

/// Parse an MPS file and return an MpsResult object (Python builds MPS dataclass from it).
#[pyfunction]
#[pyo3(signature = (path, sense, drop_cons_names=false))]
pub fn read_mps(
    py: Python<'_>,
    path: &str,
    sense: i32,
    drop_cons_names: bool,
) -> PyResult<MpsResult> {
    let content = std::fs::read_to_string(path)
        .map_err(|e| PyRuntimeError::new_err(format!("Cannot read file: {}", e)))?;

    let mut mode: Option<MpsParseMode> = None;
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
        if let Some(section) = MpsSection::from_token(tokens[0]) {
            match section {
                MpsSection::Endata => break,
                MpsSection::Comment => continue,
                MpsSection::Name => {
                    name = if tokens.len() > 1 {
                        tokens[1].to_string()
                    } else {
                        String::new()
                    };
                    continue;
                }
                MpsSection::Rows => {
                    mode = Some(MpsParseMode::Rows);
                    continue;
                }
                MpsSection::Columns => {
                    mode = Some(MpsParseMode::Columns);
                    continue;
                }
                MpsSection::Rhs if tokens.len() <= 2 => {
                    if tokens.len() > 1 {
                        rhs_names.push(tokens[1].to_string());
                        mode = Some(MpsParseMode::RhsNamed);
                    } else {
                        mode = Some(MpsParseMode::RhsUnnamed);
                    }
                    continue;
                }
                MpsSection::Bounds if tokens.len() <= 2 => {
                    if tokens.len() > 1 {
                        bnd_names.push(tokens[1].to_string());
                        mode = Some(MpsParseMode::BoundsNamed);
                    } else {
                        mode = Some(MpsParseMode::BoundsUnnamed);
                    }
                    continue;
                }
                MpsSection::Rhs | MpsSection::Bounds => {
                    // Line is "RHS name row val ..." or "BOUNDS type name val ..."; fall through to mode handling
                }
            }
        }

        if let Some(current_mode) = mode {
            match current_mode {
                MpsParseMode::Rows => {
                    let row_name = tokens[1];
                    match MpsRowType::from_token(tokens[0]) {
                        Some(MpsRowType::Objective) => obj_name = row_name.to_string(),
                        Some(rt) => {
                            constraints.insert(
                                row_name.to_string(),
                                MpsConstraintData {
                                    name: row_name.to_string(),
                                    sense: rt.sense_val(),
                                    coefficients: Vec::new(),
                                    pi: None,
                                    constant: 0.0,
                                },
                            );
                        }
                        None => {
                            return Err(PyRuntimeError::new_err(format!(
                                "Unknown row type: {}",
                                tokens[0]
                            )))
                        }
                    }
                }
                MpsParseMode::Columns => {
                    let var_name = tokens[0];
                    if tokens.len() > 1 && tokens[1] == MPS_COLUMNS_MARKER {
                        if let Some(marker) = tokens.get(2).and_then(|t| MpsMarker::from_token(t)) {
                            integral_marker = marker == MpsMarker::IntOrg;
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
                }
                MpsParseMode::RhsNamed => {
                    if tokens[0] != rhs_names.last().unwrap_or(&String::new()).as_str() {
                        return Err(PyRuntimeError::new_err(
                            "Other RHS name was given even though name was set after RHS tag.",
                        ));
                    }
                    set_rhs(&tokens, &mut constraints)?;
                }
                MpsParseMode::RhsUnnamed => {
                    set_rhs(&tokens, &mut constraints)?;
                    let rn = tokens[0].to_string();
                    if !rhs_names.contains(&rn) {
                        rhs_names.push(rn);
                    }
                }
                MpsParseMode::BoundsNamed => {
                    if tokens.len() > 1
                        && tokens[1] != bnd_names.last().unwrap_or(&String::new()).as_str()
                    {
                        return Err(PyRuntimeError::new_err(
                            "Other BOUNDS name was given even though name was set after BOUNDS tag.",
                        ));
                    }
                    set_bounds(&tokens, &mut variables)?;
                }
                MpsParseMode::BoundsUnnamed => {
                    set_bounds(&tokens, &mut variables)?;
                    if tokens.len() > 1 {
                        let bn = tokens[1].to_string();
                        if !bnd_names.contains(&bn) {
                            bnd_names.push(bn);
                        }
                    }
                }
            }
        }
    }

    let parameters = Py::new(
        py,
        MpsParameters {
            name,
            sense,
            status: 0,
            sol_status: 0,
        },
    )?;

    let obj_coeff_list = PyList::empty(py);
    for (vname, coeff) in &obj_coeffs {
        let c = MpsCoefficient {
            name: vname.clone(),
            value: *coeff,
        };
        obj_coeff_list.append(Py::new(py, c)?)?;
    }
    let objective = Py::new(
        py,
        MpsObjective {
            name: if drop_cons_names {
                None
            } else {
                Some(obj_name)
            },
            coefficients: obj_coeff_list.into_pyobject(py)?.unbind().into(),
        },
    )?;

    let var_list = PyList::empty(py);
    for vd in variables.into_values() {
        let v = MpsVariable {
            name: vd.name,
            cat: vd.cat.to_string(),
            low_bound: vd.low_bound,
            up_bound: vd.up_bound,
            var_value: vd.var_value,
            dj: vd.dj,
        };
        var_list.append(Py::new(py, v)?)?;
    }

    let constr_list = PyList::empty(py);
    for cd in constraints.into_values() {
        let coeff_list = PyList::empty(py);
        for (vname, coeff) in &cd.coefficients {
            let cc = MpsCoefficient {
                name: vname.clone(),
                value: *coeff,
            };
            coeff_list.append(Py::new(py, cc)?)?;
        }
        let c = MpsConstraint {
            name: if drop_cons_names {
                None
            } else {
                Some(cd.name)
            },
            sense: cd.sense,
            coefficients: coeff_list.into_pyobject(py)?.unbind().into(),
            pi: cd.pi,
            constant: cd.constant,
        };
        constr_list.append(Py::new(py, c)?)?;
    }

    let sos1 = PyList::empty(py).into_pyobject(py)?.unbind();
    let sos2 = PyList::empty(py).into_pyobject(py)?.unbind();

    Ok(MpsResult {
        parameters,
        objective,
        variables: var_list.into_pyobject(py)?.unbind().into(),
        constraints: constr_list.into_pyobject(py)?.unbind().into(),
        sos1: sos1.into(),
        sos2: sos2.into(),
    })
}

// ── Internal helpers (MPS parsing only) ──

/// First token on a line: section header or comment.
#[derive(Clone, Copy, PartialEq, Eq)]
enum MpsSection {
    Name,
    Rows,
    Columns,
    Rhs,
    Bounds,
    Endata,
    Comment,
}

impl MpsSection {
    fn from_token(s: &str) -> Option<Self> {
        match s {
            "NAME" => Some(MpsSection::Name),
            "ROWS" => Some(MpsSection::Rows),
            "COLUMNS" => Some(MpsSection::Columns),
            "RHS" => Some(MpsSection::Rhs),
            "BOUNDS" => Some(MpsSection::Bounds),
            "ENDATA" => Some(MpsSection::Endata),
            "*" => Some(MpsSection::Comment),
            _ => None,
        }
    }

    /// Token as written in MPS files (for write_mps).
    fn as_token(self) -> &'static str {
        match self {
            MpsSection::Name => "NAME",
            MpsSection::Rows => "ROWS",
            MpsSection::Columns => "COLUMNS",
            MpsSection::Rhs => "RHS",
            MpsSection::Bounds => "BOUNDS",
            MpsSection::Endata => "ENDATA",
            MpsSection::Comment => "*",
        }
    }
}

/// Parser state: which section we are in.
#[derive(Clone, Copy, PartialEq, Eq)]
enum MpsParseMode {
    Rows,
    Columns,
    RhsNamed,
    RhsUnnamed,
    BoundsNamed,
    BoundsUnnamed,
}

/// Row type in ROWS section: N = objective, L/E/G = constraint sense.
#[derive(Clone, Copy, PartialEq, Eq)]
enum MpsRowType {
    Objective,
    LessEqual,
    Equal,
    GreaterEqual,
}

impl MpsRowType {
    fn from_token(s: &str) -> Option<Self> {
        match s {
            "N" => Some(MpsRowType::Objective),
            "L" => Some(MpsRowType::LessEqual),
            "E" => Some(MpsRowType::Equal),
            "G" => Some(MpsRowType::GreaterEqual),
            _ => None,
        }
    }

    /// Row type code as written in MPS ROWS section (for write_mps).
    fn as_token(self) -> &'static str {
        match self {
            MpsRowType::Objective => "N",
            MpsRowType::LessEqual => "L",
            MpsRowType::Equal => "E",
            MpsRowType::GreaterEqual => "G",
        }
    }

    fn sense_val(self) -> i32 {
        match self {
            MpsRowType::Objective => 0,
            MpsRowType::LessEqual => -1,
            MpsRowType::Equal => 0,
            MpsRowType::GreaterEqual => 1,
        }
    }
}

/// Maps constraint sense to MPS row type for writing.
fn sense_to_mps_row_type(sense: Sense) -> MpsRowType {
    match sense {
        Sense::LessEqual => MpsRowType::LessEqual,
        Sense::Equal => MpsRowType::Equal,
        Sense::GreaterEqual => MpsRowType::GreaterEqual,
    }
}

/// Marker in COLUMNS: integer variable range.
#[derive(Clone, Copy, PartialEq, Eq)]
enum MpsMarker {
    IntOrg,
    IntEnd,
}

impl MpsMarker {
    fn from_token(s: &str) -> Option<Self> {
        match s {
            "'INTORG'" => Some(MpsMarker::IntOrg),
            "'INTEND'" => Some(MpsMarker::IntEnd),
            _ => None,
        }
    }

    /// Marker value as written in MPS COLUMNS section (for write_mps).
    fn as_token(self) -> &'static str {
        match self {
            MpsMarker::IntOrg => "'INTORG'",
            MpsMarker::IntEnd => "'INTEND'",
        }
    }
}

/// Literal for COLUMNS marker line (value is then INTORG or INTEND).
const MPS_COLUMNS_MARKER: &str = "'MARKER'";

/// Bound type in BOUNDS section.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum MpsBoundType {
    Fr,
    Bv,
    Pl,
    Mi,
    Lo,
    Up,
    Fx,
}

impl MpsBoundType {
    fn from_token(s: &str) -> Option<Self> {
        match s {
            "FR" => Some(MpsBoundType::Fr),
            "BV" => Some(MpsBoundType::Bv),
            "PL" => Some(MpsBoundType::Pl),
            "MI" => Some(MpsBoundType::Mi),
            "LO" => Some(MpsBoundType::Lo),
            "UP" => Some(MpsBoundType::Up),
            "FX" => Some(MpsBoundType::Fx),
            _ => None,
        }
    }
}

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

// ── PyO3 classes for MPS result (exposed to Python) ──

#[pyclass]
pub struct MpsParameters {
    name: String,
    sense: i32,
    status: i32,
    sol_status: i32,
}

#[pymethods]
impl MpsParameters {
    #[getter]
    fn name(&self) -> &str {
        &self.name
    }
    #[getter]
    fn sense(&self) -> i32 {
        self.sense
    }
    #[getter]
    fn status(&self) -> i32 {
        self.status
    }
    #[getter]
    fn sol_status(&self) -> i32 {
        self.sol_status
    }
}

#[pyclass]
pub struct MpsCoefficient {
    name: String,
    value: f64,
}

#[pymethods]
impl MpsCoefficient {
    #[getter]
    fn name(&self) -> &str {
        &self.name
    }
    #[getter]
    fn value(&self) -> f64 {
        self.value
    }
}

#[pyclass]
pub struct MpsObjective {
    name: Option<String>,
    coefficients: Py<PyAny>,
}

#[pymethods]
impl MpsObjective {
    #[getter]
    fn name(&self, py: Python<'_>) -> Py<PyAny> {
        match &self.name {
            Some(s) => PyString::new(py, s).unbind().into(),
            None => py.None(),
        }
    }
    #[getter]
    fn coefficients(&self, py: Python<'_>) -> Py<PyAny> {
        self.coefficients.clone_ref(py)
    }
}

#[pyclass]
pub struct MpsVariable {
    name: String,
    cat: String,
    low_bound: Option<f64>,
    up_bound: Option<f64>,
    var_value: Option<f64>,
    dj: Option<f64>,
}

#[pymethods]
impl MpsVariable {
    #[getter]
    fn name(&self) -> &str {
        &self.name
    }
    #[getter]
    fn cat(&self) -> &str {
        &self.cat
    }
    #[getter(lowBound)]
    fn low_bound(&self, py: Python<'_>) -> Py<PyAny> {
        match self.low_bound {
            Some(v) => PyFloat::new(py, v).unbind().into(),
            None => py.None(),
        }
    }
    #[getter(upBound)]
    fn up_bound(&self, py: Python<'_>) -> Py<PyAny> {
        match self.up_bound {
            Some(v) => PyFloat::new(py, v).unbind().into(),
            None => py.None(),
        }
    }
    #[getter(varValue)]
    fn var_value(&self, py: Python<'_>) -> Py<PyAny> {
        match self.var_value {
            Some(v) => PyFloat::new(py, v).unbind().into(),
            None => py.None(),
        }
    }
    #[getter]
    fn dj(&self, py: Python<'_>) -> Py<PyAny> {
        match self.dj {
            Some(v) => PyFloat::new(py, v).unbind().into(),
            None => py.None(),
        }
    }
}

#[pyclass]
pub struct MpsConstraint {
    name: Option<String>,
    sense: i32,
    coefficients: Py<PyAny>,
    pi: Option<f64>,
    constant: f64,
}

#[pymethods]
impl MpsConstraint {
    #[getter]
    fn name(&self, py: Python<'_>) -> Py<PyAny> {
        match &self.name {
            Some(s) => PyString::new(py, s).unbind().into(),
            None => py.None(),
        }
    }
    #[getter]
    fn sense(&self) -> i32 {
        self.sense
    }
    #[getter]
    fn coefficients(&self, py: Python<'_>) -> Py<PyAny> {
        self.coefficients.clone_ref(py)
    }
    #[getter]
    fn pi(&self, py: Python<'_>) -> Py<PyAny> {
        match self.pi {
            Some(v) => PyFloat::new(py, v).unbind().into(),
            None => py.None(),
        }
    }
    #[getter]
    fn constant(&self) -> f64 {
        self.constant
    }
}

#[pyclass]
pub struct MpsResult {
    parameters: Py<MpsParameters>,
    objective: Py<MpsObjective>,
    variables: Py<PyAny>,
    constraints: Py<PyAny>,
    sos1: Py<PyAny>,
    sos2: Py<PyAny>,
}

#[pymethods]
impl MpsResult {
    #[getter]
    fn parameters(&self, py: Python<'_>) -> Py<MpsParameters> {
        self.parameters.clone_ref(py)
    }
    #[getter]
    fn objective(&self, py: Python<'_>) -> Py<MpsObjective> {
        self.objective.clone_ref(py)
    }
    #[getter]
    fn variables(&self, py: Python<'_>) -> Py<PyAny> {
        self.variables.clone_ref(py)
    }
    #[getter]
    fn constraints(&self, py: Python<'_>) -> Py<PyAny> {
        self.constraints.clone_ref(py)
    }
    #[getter]
    fn sos1(&self, py: Python<'_>) -> Py<PyAny> {
        self.sos1.clone_ref(py)
    }
    #[getter]
    fn sos2(&self, py: Python<'_>) -> Py<PyAny> {
        self.sos2.clone_ref(py)
    }
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
    let var_name = tokens[2];
    let Some(vd) = variables.get_mut(var_name) else {
        return Ok(());
    };
    let Some(bound) = MpsBoundType::from_token(tokens[0]) else {
        return Err(PyRuntimeError::new_err(format!(
            "Unknown bound type: {}",
            tokens[0]
        )));
    };
    match bound {
        MpsBoundType::Fr => {
            vd.low_bound = None;
            vd.up_bound = None;
        }
        MpsBoundType::Bv => {
            vd.low_bound = Some(0.0);
            vd.up_bound = Some(1.0);
        }
        MpsBoundType::Pl => {
            vd.low_bound = Some(0.0);
            vd.up_bound = None;
        }
        MpsBoundType::Mi => {
            vd.low_bound = None;
        }
        MpsBoundType::Lo | MpsBoundType::Up | MpsBoundType::Fx => {
            if tokens.len() < 4 {
                return Err(PyRuntimeError::new_err(format!(
                    "Missing value for bound type {:?}",
                    bound
                )));
            }
            let val: f64 = tokens[3]
                .parse()
                .map_err(|e| PyRuntimeError::new_err(format!("Parse error: {}", e)))?;
            match bound {
                MpsBoundType::Lo => vd.low_bound = Some(val),
                MpsBoundType::Up => vd.up_bound = Some(val),
                MpsBoundType::Fx => {
                    vd.low_bound = Some(val);
                    vd.up_bound = Some(val);
                }
                _ => unreachable!(),
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod write_mps_buffer_tests {
    use indexmap::IndexMap;

    use super::*;
    use crate::affine_expr::AffineExpr;
    use crate::types::{Category, ConstraintData, ObjSense, Sense};

    fn constraint(
        terms: Vec<(VarId, f64)>,
        constant: f64,
        sense: Sense,
        name: &str,
    ) -> AffineExpr {
        AffineExpr {
            terms: terms.into_iter().collect(),
            constant,
            sense: Some(sense),
            name: Some(name.to_string()),
            model: None,
        }
    }

    fn objective(terms: Vec<(VarId, f64)>) -> AffineExpr {
        AffineExpr {
            terms: terms.into_iter().collect(),
            constant: 0.0,
            sense: None,
            name: Some("obj".to_string()),
            model: None,
        }
    }

    fn build_continuous_core() -> ModelCore {
        let mut core = ModelCore::new("continuous".to_string());
        let x = core.add_variable("x".to_string(), 0.0, 4.0, Category::Continuous);
        let y = core.add_variable("y".to_string(), -1.0, 1.0, Category::Continuous);
        let z = core.add_variable("z".to_string(), 0.0, f64::INFINITY, Category::Continuous);
        core.set_objective(objective(vec![(x, 1.0), (y, 4.0), (z, 9.0)]));
        core.add_constraint(&constraint(
            vec![(x, 1.0), (y, 1.0)],
            -5.0,
            Sense::LessEqual,
            "c1",
        ))
        .unwrap();
        core.add_constraint(&constraint(
            vec![(x, 1.0), (z, 1.0)],
            -10.0,
            Sense::GreaterEqual,
            "c2",
        ))
        .unwrap();
        core.add_constraint(&constraint(
            vec![(y, -1.0), (z, 1.0)],
            -7.0,
            Sense::Equal,
            "c3",
        ))
        .unwrap();
        core
    }

    fn build_integer_core() -> ModelCore {
        let mut core = ModelCore::new("integer".to_string());
        let x = core.add_variable("x".to_string(), 0.0, 4.0, Category::Continuous);
        let y = core.add_variable("y".to_string(), -1.0, 1.0, Category::Continuous);
        let z = core.add_variable("z".to_string(), 0.0, f64::INFINITY, Category::Integer);
        core.set_objective(objective(vec![(x, 1.1), (y, 4.1), (z, 9.1)]));
        core.add_constraint(&constraint(
            vec![(x, 1.0), (y, 1.0)],
            -5.0,
            Sense::LessEqual,
            "c1",
        ))
        .unwrap();
        core.add_constraint(&constraint(
            vec![(x, 1.0), (z, 1.0)],
            -10.0,
            Sense::GreaterEqual,
            "c2",
        ))
        .unwrap();
        core.add_constraint(&constraint(
            vec![(y, -1.0), (z, 1.0)],
            -7.5,
            Sense::Equal,
            "c3",
        ))
        .unwrap();
        core
    }

    fn build_binary_core() -> ModelCore {
        let mut core = ModelCore::new("binary".to_string());
        core.sense = ObjSense::Maximize;
        let dummy = core.add_variable(
            "dummy".to_string(),
            f64::NEG_INFINITY,
            f64::INFINITY,
            Category::Continuous,
        );
        let c1 = core.add_variable("c1".to_string(), 0.0, 1.0, Category::Binary);
        let c2 = core.add_variable("c2".to_string(), 0.0, 1.0, Category::Binary);
        core.set_objective(AffineExpr {
            terms: IndexMap::from([(dummy, 1.0)]),
            constant: 0.0,
            sense: None,
            name: Some("OBJ".to_string()),
            model: None,
        });
        core.constraints.push(ConstraintData {
            name: "_C1".to_string(),
            coeffs: IndexMap::from([(c1, 1.0), (c2, 1.0)]),
            rhs: 2.0,
            sense: Sense::Equal,
            pi: None,
            slack: None,
        });
        core.constraints.push(ConstraintData {
            name: "_C2".to_string(),
            coeffs: IndexMap::from([(c1, 1.0)]),
            rhs: 0.0,
            sense: Sense::LessEqual,
            pi: None,
            slack: None,
        });
        core
    }

    fn build_rename_core() -> ModelCore {
        let mut core = ModelCore::new("rename".to_string());
        let x = core.add_variable("x".to_string(), 0.0, 1.0, Category::Integer);
        let y = core.add_variable("y".to_string(), 0.0, 1.0, Category::Integer);
        core.set_objective(objective(vec![(x, 1.0), (y, 2.0)]));
        core.add_constraint(&constraint(
            vec![(x, 1.0), (y, 1.0)],
            -1.0,
            Sense::LessEqual,
            "c1",
        ))
        .unwrap();
        core.add_constraint(&constraint(
            vec![(x, 1.0), (y, -1.0)],
            0.0,
            Sense::GreaterEqual,
            "c2",
        ))
        .unwrap();
        core
    }

    fn build_objsense_max_core() -> ModelCore {
        let mut core = ModelCore::new("objsense_max".to_string());
        core.sense = ObjSense::Maximize;
        let x = core.add_variable("x".to_string(), 0.0, 4.0, Category::Continuous);
        let y = core.add_variable("y".to_string(), -1.0, 1.0, Category::Continuous);
        core.set_objective(objective(vec![(x, 1.0), (y, 4.0)]));
        core.add_constraint(&constraint(
            vec![(x, 1.0), (y, 1.0)],
            -5.0,
            Sense::LessEqual,
            "c1",
        ))
        .unwrap();
        core.add_constraint(&constraint(vec![(x, 1.0)], 0.0, Sense::GreaterEqual, "c2"))
            .unwrap();
        core
    }

    macro_rules! golden_test {
        ($name:ident, $builder:ident, $fixture:literal, $mps_sense:expr, $mip:expr, $with_objsense:expr, $rename:expr, $model_name:literal, $obj_name:literal) => {
            #[test]
            fn $name() {
                let core = $builder();
                let got = write_mps_buffer(
                    &core,
                    $mps_sense,
                    $mip,
                    $with_objsense,
                    $rename,
                    $model_name,
                    $obj_name,
                )
                .unwrap();
                let want = include_bytes!(concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/pulp/tests/fixtures/mps/",
                    $fixture
                ));
                assert_eq!(
                    got.as_slice(),
                    want.as_slice(),
                    "golden mismatch for {}",
                    $fixture
                );
            }
        };
    }

    golden_test!(
        write_mps_buffer_matches_golden_continuous,
        build_continuous_core,
        "continuous.mps",
        1,
        false,
        false,
        false,
        "continuous",
        "obj"
    );
    golden_test!(
        write_mps_buffer_matches_golden_integer,
        build_integer_core,
        "integer.mps",
        1,
        true,
        false,
        false,
        "integer",
        "obj"
    );
    golden_test!(
        write_mps_buffer_matches_golden_binary,
        build_binary_core,
        "binary.mps",
        -1,
        true,
        false,
        false,
        "binary",
        "OBJ"
    );
    golden_test!(
        write_mps_buffer_matches_golden_rename,
        build_rename_core,
        "rename.mps",
        1,
        true,
        false,
        true,
        "rename",
        "obj"
    );
    golden_test!(
        write_mps_buffer_matches_golden_objsense_max,
        build_objsense_max_core,
        "objsense_max.mps",
        -1,
        false,
        true,
        false,
        "objsense_max",
        "obj"
    );

    #[test]
    fn write_mps_buffer_roundtrip_read_mps() {
        let core = build_continuous_core();
        let bytes = write_mps_buffer(&core, 1, false, false, false, "continuous", "obj")
            .unwrap();
        let text = std::str::from_utf8(&bytes).unwrap();
        assert!(text.contains("NAME          continuous"));
        assert!(text.contains("COLUMNS"));
        assert!(text.contains("ENDATA"));
    }
}
