//! Python-exposed Model (high-level handle to ModelCore).

use std::sync::Arc;
use std::sync::Mutex;

use indexmap::IndexMap;
use pyo3::prelude::*;

use crate::affine_expr::AffineExpr;
use crate::constraint::Constraint;
use crate::types::{
    get_model_optional, lock_model, upgrade_model, Category, ChangeLog, ConstrId, ModelCore,
    ObjSense, SharedModelCore, SosGroup, SosKind, VarId,
};
use crate::variable::Variable;

/// High-level model handle exposed to Python.
#[pyclass]
pub struct Model {
    pub core: SharedModelCore,
}

impl Model {
    /// Wrap an existing core (same `Arc` as variables). Used by `Variable::containing_model`.
    pub(crate) fn from_shared_core(core: SharedModelCore) -> Self {
        Self { core }
    }
}

#[pymethods]
impl Model {
    #[new]
    fn new(name: Option<String>) -> Self {
        let name = name.unwrap_or_else(|| "Model".to_string());
        let core = Arc::new(Mutex::new(ModelCore::new(name)));
        Self { core }
    }

    fn add_variable(
        &mut self,
        name: String,
        lb: f64,
        ub: f64,
        category: Category,
    ) -> Variable {
        let id = lock_model(&self.core).add_variable(name, lb, ub, category);
        Variable {
            id,
            model: Arc::downgrade(&self.core),
        }
    }

    fn add_constraint(&mut self, expr: &AffineExpr) -> PyResult<Constraint> {
        let mut e = expr.clone();
        if e.model.is_none() {
            e.model = Some(Arc::downgrade(&self.core));
        } else {
            let expr_core = get_model_optional(&e.model)?;
            if !Arc::ptr_eq(&expr_core, &self.core) {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Expression is bound to a different model than the one receiving the constraint.",
                ));
            }
        }
        let id = lock_model(&self.core).add_constraint(&e)?;
        Ok(Constraint {
            id,
            model: Arc::downgrade(&self.core),
        })
    }

    fn set_objective(&mut self, expr: &AffineExpr) {
        let mut stored = expr.clone();
        if stored.model.is_none() {
            stored.model = Some(Arc::downgrade(&self.core));
        }
        lock_model(&self.core).set_objective(stored);
    }

    /// Add a variable column-wise: its objective coefficient and its
    /// coefficients in existing constraints (`entries`, `(constraint id,
    /// coefficient)` pairs; zeros are skipped). Validates everything before
    /// changing the model.
    fn add_column(
        &mut self,
        name: String,
        lb: f64,
        ub: f64,
        category: Category,
        obj_coeff: f64,
        entries: Vec<(ConstrId, f64)>,
    ) -> PyResult<Variable> {
        let mut core = lock_model(&self.core);
        if !obj_coeff.is_finite() {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Invalid objective coefficient value: {obj_coeff}. Coefficients must be finite."
            )));
        }
        let n = core.constraints.len();
        for &(cid, coeff) in &entries {
            if cid >= n {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "Constraint id {cid} is out of range (model has {n} constraints)"
                )));
            }
            if !coeff.is_finite() {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "Invalid coefficient value: {coeff} in constraint id {cid}. Coefficients must be finite."
                )));
            }
        }
        let id = core.add_variable(name, lb, ub, category);
        for (cid, coeff) in entries {
            core.set_coefficient(cid, id, coeff)?;
        }
        if obj_coeff != 0.0 {
            let weak = Arc::downgrade(&self.core);
            let obj = core.objective.get_or_insert_with(|| AffineExpr {
                terms: IndexMap::new(),
                constant: 0.0,
                sense: None,
                name: None,
                model: Some(weak),
            });
            obj.terms.insert(id, obj_coeff);
        }
        core.changes.obj_coeff(id);
        Ok(Variable {
            id,
            model: Arc::downgrade(&self.core),
        })
    }

    /// Drop the variables `ids` from every constraint, the objective and every
    /// SOS group (see `ModelCore::remove_variables`).
    fn remove_variables(&mut self, ids: Vec<VarId>) -> PyResult<()> {
        lock_model(&self.core).remove_variables(&ids)
    }

    fn set_sense(&mut self, sense: ObjSense) {
        let mut core = lock_model(&self.core);
        if core.sense != sense {
            core.changes.sense_changed = true;
        }
        core.sense = sense;
    }

    /// Start recording edits for a solver that has just loaded the whole
    /// model; collect them with [`take_changes`](Self::take_changes).
    fn track_changes(&mut self) {
        let mut core = lock_model(&self.core);
        let (cols, rows) = (core.vars.len(), core.constraints.len());
        core.changes.start(cols, rows);
    }

    /// Stop recording edits (the solver's copy can no longer be updated).
    fn stop_tracking(&mut self) {
        lock_model(&self.core).changes = ChangeLog::default();
    }

    /// The current coefficient of each `(constraint id, variable id)` entry,
    /// 0 where the variable is not in the constraint.
    fn coefficients_at(&self, entries: Vec<(ConstrId, VarId)>) -> PyResult<Vec<f64>> {
        let core = lock_model(&self.core);
        let n = core.constraints.len();
        entries
            .into_iter()
            .map(|(cid, vid)| {
                let cd = core.constraints.get(cid).ok_or_else(|| {
                    pyo3::exceptions::PyIndexError::new_err(format!(
                        "Constraint id {cid} is out of range (model has {n} constraints)"
                    ))
                })?;
                Ok(cd.coeffs.get(&vid).copied().unwrap_or(0.0))
            })
            .collect()
    }

    /// The objective coefficient of each variable id, 0 where it is not in
    /// the objective.
    fn objective_coefficients(&self, ids: Vec<VarId>) -> Vec<f64> {
        let core = lock_model(&self.core);
        match &core.objective {
            None => vec![0.0; ids.len()],
            Some(obj) => ids
                .iter()
                .map(|vid| obj.terms.get(vid).copied().unwrap_or(0.0))
                .collect(),
        }
    }

    /// Whether edits are being recorded (see [`track_changes`](Self::track_changes)).
    #[getter]
    fn tracking_changes(&self) -> bool {
        lock_model(&self.core).changes.enabled
    }

    /// The edits recorded since [`track_changes`](Self::track_changes) or the
    /// previous call, which the solver is expected to apply now: recording
    /// starts over with the model as it is.
    fn take_changes(&mut self) -> PyResult<ModelChanges> {
        let mut core = lock_model(&self.core);
        if !core.changes.enabled {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Changes are not being tracked; call track_changes() first.",
            ));
        }
        let (cols, rows) = (core.vars.len(), core.constraints.len());
        let log = std::mem::take(&mut core.changes);
        core.changes.start(cols, rows);
        Ok(ModelChanges::from_log(log, cols, rows))
    }

    fn clear_objective(&mut self) {
        lock_model(&self.core).clear_objective();
    }

    fn add_variables_batch(
        &mut self,
        names: Vec<String>,
        lb: f64,
        ub: f64,
        category: Category,
    ) -> Vec<Variable> {
        let n = names.len();
        let start_id = lock_model(&self.core).vars.len();
        let mut core = lock_model(&self.core);
        for name in names {
            core.add_variable(name, lb, ub, category);
        }
        (start_id..start_id + n)
            .map(|id| Variable {
                id,
                model: Arc::downgrade(&self.core),
            })
            .collect()
    }

    pub fn get_variable(&self, id: VarId) -> Variable {
        Variable {
            id,
            model: Arc::downgrade(&self.core),
        }
    }

    fn list_variables(&self) -> Vec<Variable> {
        let n = lock_model(&self.core).vars.len();
        (0..n)
            .map(|id| Variable {
                id,
                model: Arc::downgrade(&self.core),
            })
            .collect()
    }

    /// Sorted unique variable ids referenced by objective, constraints, and SOS.
    fn used_variable_ids(&self) -> Vec<VarId> {
        lock_model(&self.core).used_var_ids()
    }

    /// `Variable` handles for each id returned by [`used_variable_ids`](Self::used_variable_ids).
    fn list_variables_by_ids(&self, ids: Vec<VarId>) -> PyResult<Vec<Variable>> {
        let n = lock_model(&self.core).vars.len();
        let weak = Arc::downgrade(&self.core);
        ids.into_iter()
            .map(|id| {
                if id >= n {
                    return Err(pyo3::exceptions::PyIndexError::new_err(format!(
                        "variable id {id} out of range (model has {n} variables)"
                    )));
                }
                Ok(Variable {
                    id,
                    model: weak.clone(),
                })
            })
            .collect()
    }

    fn clear_sos(&mut self) {
        lock_model(&self.core).clear_sos();
    }

    /// Append one SOS group. Each `Variable` must belong to this model.
    /// `(sos_type, optional_key, list of (var_id, weight))` with `sos_type` 1 = SOS1, 2 = SOS2.
    fn sos_export(&self) -> Vec<(i32, Option<String>, Vec<(VarId, f64)>)> {
        let core = lock_model(&self.core);
        core.sos
            .iter()
            .map(|g| {
                let t = match g.kind {
                    SosKind::Sos1 => 1,
                    SosKind::Sos2 => 2,
                };
                (t, g.key.clone(), g.weights.clone())
            })
            .collect()
    }

    fn add_sos_group(
        &mut self,
        kind: SosKind,
        key: Option<String>,
        members: Vec<(Variable, f64)>,
    ) -> PyResult<()> {
        let mut weights = Vec::with_capacity(members.len());
        for (v, w) in members {
            let core_rc = upgrade_model(&v.model)?;
            if !Arc::ptr_eq(&core_rc, &self.core) {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "SOS member variable belongs to a different model",
                ));
            }
            if !w.is_finite() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "SOS weight must be finite",
                ));
            }
            weights.push((v.id, w));
        }
        lock_model(&self.core).push_sos_group(SosGroup {
            kind,
            key,
            weights,
        });
        Ok(())
    }

    fn get_constraint(&self, id: ConstrId) -> PyResult<Constraint> {
        let n = lock_model(&self.core).constraints.len();
        if id >= n {
            return Err(pyo3::exceptions::PyIndexError::new_err(format!(
                "Constraint id {id} is out of range (model has {n} constraints)"
            )));
        }
        Ok(Constraint {
            id,
            model: Arc::downgrade(&self.core),
        })
    }

    fn list_constraints(&self) -> Vec<Constraint> {
        let n = lock_model(&self.core).constraints.len();
        (0..n)
            .map(|id| Constraint {
                id,
                model: Arc::downgrade(&self.core),
            })
            .collect()
    }

    fn get_objective(&self) -> Option<AffineExpr> {
        let core = lock_model(&self.core);
        core.objective.clone()
    }

    fn get_sense(&self) -> ObjSense {
        lock_model(&self.core).sense
    }

    #[getter]
    fn num_variables(&self) -> usize {
        lock_model(&self.core).vars.len()
    }

    #[getter]
    fn num_constraints(&self) -> usize {
        lock_model(&self.core).constraints.len()
    }

    fn summary(&self) -> String {
        let core = lock_model(&self.core);
        format!(
            "Model(name={}, vars={}, constraints={}, objective={})",
            core.name,
            core.vars.len(),
            core.constraints.len(),
            if core.objective.is_some() {
                "set"
            } else {
                "unset"
            }
        )
    }

    fn set_variable_values(&self, values: Vec<(VarId, f64)>) {
        let mut core = lock_model(&self.core);
        for (id, val) in values {
            if let Some(v) = core.vars.get_mut(id) {
                v.value = Some(val);
            }
        }
    }

    fn set_variable_djs(&self, values: Vec<(VarId, f64)>) {
        let mut core = lock_model(&self.core);
        for (id, val) in values {
            if let Some(v) = core.vars.get_mut(id) {
                v.dj = Some(val);
            }
        }
    }

    fn set_constraint_pis(&self, values: Vec<(ConstrId, f64)>) {
        let mut core = lock_model(&self.core);
        for (id, val) in values {
            if let Some(c) = core.constraints.get_mut(id) {
                c.pi = Some(val);
            }
        }
    }

    fn set_constraint_slacks(&self, values: Vec<(ConstrId, f64)>) {
        let mut core = lock_model(&self.core);
        for (id, val) in values {
            if let Some(c) = core.constraints.get_mut(id) {
                c.slack = Some(val);
            }
        }
    }

    fn set_variable_values_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = lock_model(&self.core);
        for v in &mut core.vars {
            if let Some(&val) = values.get(&v.name) {
                v.value = Some(val);
            }
        }
    }

    fn set_variable_djs_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = lock_model(&self.core);
        for v in &mut core.vars {
            if let Some(&val) = values.get(&v.name) {
                v.dj = Some(val);
            }
        }
    }

    fn set_constraint_pis_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = lock_model(&self.core);
        for c in &mut core.constraints {
            if let Some(&val) = values.get(&c.name) {
                c.pi = Some(val);
            }
        }
    }

    fn set_constraint_slacks_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = lock_model(&self.core);
        for c in &mut core.constraints {
            if let Some(&val) = values.get(&c.name) {
                c.slack = Some(val);
            }
        }
    }

    fn constraints_dict(&self) -> Vec<(String, Constraint)> {
        let core = lock_model(&self.core);
        core.constraints
            .iter()
            .enumerate()
            .map(|(id, c)| {
                (
                    c.name.clone(),
                    Constraint {
                        id,
                        model: Arc::downgrade(&self.core),
                    },
                )
            })
            .collect()
    }

    fn variables_dict(&self) -> Vec<(String, Variable)> {
        let core = lock_model(&self.core);
        core.vars
            .iter()
            .enumerate()
            .map(|(id, v)| {
                (
                    v.name.clone(),
                    Variable {
                        id,
                        model: Arc::downgrade(&self.core),
                    },
                )
            })
            .collect()
    }

    fn get_constraint_by_name(&self, name: &str) -> Option<Constraint> {
        let core = lock_model(&self.core);
        core.constraints
            .iter()
            .enumerate()
            .find(|(_, c)| c.name == name)
            .map(|(id, _)| Constraint {
                id,
                model: Arc::downgrade(&self.core),
            })
    }

    // ── Phase 3 methods ──

    /// Whether any variable is Integer or Binary.
    fn is_mip(&self) -> bool {
        let core = lock_model(&self.core);
        core.vars
            .iter()
            .any(|v| v.category == Category::Integer || v.category == Category::Binary)
    }

    /// Round all variable values to bounds and integrality.
    #[pyo3(signature = (eps_int=1e-5, eps=1e-7))]
    fn round_solution(&self, eps_int: f64, eps: f64) {
        let mut core = lock_model(&self.core);
        for vd in &mut core.vars {
            if let Some(val) = vd.value {
                let mut v = val;
                if vd.ub.is_finite() && v > vd.ub && v <= vd.ub + eps {
                    v = vd.ub;
                } else if vd.lb.is_finite() && v < vd.lb && v >= vd.lb - eps {
                    v = vd.lb;
                }
                if vd.category == Category::Integer && (v - v.round()).abs() <= eps_int {
                    v = v.round();
                }
                vd.value = Some(v);
            }
        }
    }

    /// Check for duplicate variable names.
    fn check_duplicate_vars(&self) -> PyResult<()> {
        lock_model(&self.core).check_duplicate_var_names()
    }

    /// Check for duplicate constraint names.
    fn check_duplicate_constraints(&self) -> PyResult<()> {
        lock_model(&self.core).check_duplicate_constraint_names()
    }

    /// Check that no variable name exceeds max_length.
    fn check_length_vars(&self, max_length: usize) -> PyResult<()> {
        lock_model(&self.core).check_var_name_lengths(max_length)
    }

    /// Return all (variable_name, constraint_name, coefficient) triples.
    fn coefficients(&self) -> Vec<(String, String, f64)> {
        let core = lock_model(&self.core);
        let mut result = Vec::new();
        for cd in &core.constraints {
            for (&vid, &coeff) in &cd.coeffs {
                let vname = core
                    .vars
                    .get(vid)
                    .map(|v| v.name.clone())
                    .unwrap_or_default();
                result.push((vname, cd.name.clone(), coeff));
            }
        }
        result
    }

    /// Deep-copy the entire model (new `Arc`, new data).
    fn copy_model(&self) -> Self {
        let core = lock_model(&self.core);
        let new_core = ModelCore {
            name: core.name.clone(),
            vars: core.vars.clone(),
            constraints: core.constraints.clone(),
            objective: core.objective.clone(),
            sense: core.sense,
            next_auto_constraint_id: core.next_auto_constraint_id,
            sos: core.sos.clone(),
            changes: ChangeLog::default(),
        };
        let new_rc = Arc::new(Mutex::new(new_core));
        {
            let mut inner = lock_model(&new_rc);
            if let Some(ref mut obj) = inner.objective {
                obj.model = Some(Arc::downgrade(&new_rc));
            }
        }
        Self { core: new_rc }
    }
}

/// Edits to a model since a solver last loaded it (see `Model.take_changes`).
#[pyclass(frozen, get_all)]
pub struct ModelChanges {
    /// A change the solver cannot replay: it must rebuild its model.
    pub unsupported: bool,
    pub sense_changed: bool,
    /// The objective was replaced or cleared: send every cost again.
    pub objective_replaced: bool,
    /// Variable ids added since: new solver columns, in order.
    pub new_cols: Vec<VarId>,
    /// Constraint ids added since: new solver rows, in order.
    pub new_rows: Vec<ConstrId>,
    /// Objective coefficients changed on existing columns.
    pub obj_coeffs: Vec<VarId>,
    /// Edited `(constraint id, variable id)` entries in existing rows. Entries
    /// with a new variable id belong to that new column.
    pub coeffs: Vec<(ConstrId, VarId)>,
    /// Existing rows whose right-hand side or sense changed.
    pub row_bounds: Vec<ConstrId>,
    /// Existing columns whose bounds changed.
    pub var_bounds: Vec<VarId>,
    /// Existing columns whose category changed.
    pub var_category: Vec<VarId>,
}

impl ModelChanges {
    fn from_log(log: ChangeLog, cols: usize, rows: usize) -> Self {
        Self {
            unsupported: log.unsupported,
            sense_changed: log.sense_changed,
            objective_replaced: log.objective_replaced,
            new_cols: (log.cols_synced..cols).collect(),
            new_rows: (log.rows_synced..rows).collect(),
            obj_coeffs: log.obj_coeffs.into_iter().collect(),
            coeffs: log.coeffs.into_iter().collect(),
            row_bounds: log.row_bounds.into_iter().collect(),
            var_bounds: log.var_bounds.into_iter().collect(),
            var_category: log.var_category.into_iter().collect(),
        }
    }
}

#[pymethods]
impl ModelChanges {
    /// True when nothing changed.
    fn is_empty(&self) -> bool {
        !self.unsupported
            && !self.sense_changed
            && !self.objective_replaced
            && self.new_cols.is_empty()
            && self.new_rows.is_empty()
            && self.obj_coeffs.is_empty()
            && self.coeffs.is_empty()
            && self.row_bounds.is_empty()
            && self.var_bounds.is_empty()
            && self.var_category.is_empty()
    }
}
