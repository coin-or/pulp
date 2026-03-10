//! Python-exposed Model (high-level handle to ModelCore).

use std::cell::RefCell;
use std::rc::Rc;

use indexmap::IndexMap;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::affine_expr::AffineExpr;
use crate::constraint::Constraint;
use crate::types::{Category, ConstrId, ModelCore, ObjSense, Sense, VarId};
use crate::variable::Variable;

/// High-level model handle exposed to Python.
#[pyclass(unsendable)]
pub struct Model {
    pub core: Rc<RefCell<ModelCore>>,
    next_constraint_id: usize,
}

#[pymethods]
impl Model {
    #[new]
    fn new(name: Option<String>) -> Self {
        let name = name.unwrap_or_else(|| "Model".to_string());
        let core = Rc::new(RefCell::new(ModelCore::new(name)));
        Self {
            core,
            next_constraint_id: 0,
        }
    }

    fn add_variable(
        &mut self,
        name: String,
        lb: f64,
        ub: f64,
        category: Category,
    ) -> Variable {
        let id = self.core.borrow_mut().add_variable(name, lb, ub, category);
        Variable {
            id,
            model: Rc::downgrade(&self.core),
        }
    }

    fn add_constraint(
        &mut self,
        name: String,
        coeffs: Vec<(Variable, f64)>,
        rhs: f64,
        sense: Sense,
    ) -> PyResult<Constraint> {
        let actual_name = if name.is_empty() {
            loop {
                self.next_constraint_id += 1;
                let candidate = format!("_C{}", self.next_constraint_id);
                let exists = self
                    .core
                    .borrow()
                    .constraints
                    .iter()
                    .any(|c| c.name == candidate);
                if !exists {
                    break candidate;
                }
            }
        } else {
            let exists = self
                .core
                .borrow()
                .constraints
                .iter()
                .any(|c| c.name == name);
            if exists {
                return Err(PyValueError::new_err(format!(
                    "Duplicate constraint name: {}",
                    name
                )));
            }
            name
        };
        let mut map = IndexMap::new();
        for (var, coeff) in coeffs {
            let entry = map.entry(var.id()).or_insert(0.0);
            *entry += coeff;
        }
        let id = self
            .core
            .borrow_mut()
            .add_constraint(actual_name, map, rhs, sense);
        Ok(Constraint {
            id,
            model: Rc::downgrade(&self.core),
        })
    }

    fn set_objective(&mut self, expr: &AffineExpr) {
        let mut stored = expr.clone();
        if stored.model.is_none() {
            stored.model = Some(Rc::downgrade(&self.core));
        }
        self.core.borrow_mut().set_objective(stored);
    }

    fn set_sense(&mut self, sense: ObjSense) {
        self.core.borrow_mut().sense = sense;
    }

    fn clear_objective(&mut self) {
        self.core.borrow_mut().clear_objective();
    }

    fn add_variables_batch(
        &mut self,
        names: Vec<String>,
        lb: f64,
        ub: f64,
        category: Category,
    ) -> Vec<Variable> {
        let n = names.len();
        let start_id = self.core.borrow().vars.len();
        {
            let mut core = self.core.borrow_mut();
            for name in names {
                core.add_variable(name, lb, ub, category);
            }
        }
        (start_id..start_id + n)
            .map(|id| Variable {
                id,
                model: Rc::downgrade(&self.core),
            })
            .collect()
    }

    pub fn get_variable(&self, id: VarId) -> Variable {
        Variable {
            id,
            model: Rc::downgrade(&self.core),
        }
    }

    fn list_variables(&self) -> Vec<Variable> {
        let n = self.core.borrow().vars.len();
        (0..n)
            .map(|id| Variable {
                id,
                model: Rc::downgrade(&self.core),
            })
            .collect()
    }

    fn list_constraints(&self) -> Vec<Constraint> {
        let n = self.core.borrow().constraints.len();
        (0..n)
            .map(|id| Constraint {
                id,
                model: Rc::downgrade(&self.core),
            })
            .collect()
    }

    fn get_objective(&self) -> Option<AffineExpr> {
        let core = self.core.borrow();
        core.objective.clone()
    }

    fn get_sense(&self) -> ObjSense {
        self.core.borrow().sense
    }

    #[getter]
    fn num_variables(&self) -> usize {
        self.core.borrow().vars.len()
    }

    #[getter]
    fn num_constraints(&self) -> usize {
        self.core.borrow().constraints.len()
    }

    fn summary(&self) -> String {
        let core = self.core.borrow();
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
        let mut core = self.core.borrow_mut();
        for (id, val) in values {
            if let Some(v) = core.vars.get_mut(id) {
                v.value = Some(val);
            }
        }
    }

    fn set_variable_djs(&self, values: Vec<(VarId, f64)>) {
        let mut core = self.core.borrow_mut();
        for (id, val) in values {
            if let Some(v) = core.vars.get_mut(id) {
                v.dj = Some(val);
            }
        }
    }

    fn set_constraint_pis(&self, values: Vec<(ConstrId, f64)>) {
        let mut core = self.core.borrow_mut();
        for (id, val) in values {
            if let Some(c) = core.constraints.get_mut(id) {
                c.pi = Some(val);
            }
        }
    }

    fn set_constraint_slacks(&self, values: Vec<(ConstrId, f64)>) {
        let mut core = self.core.borrow_mut();
        for (id, val) in values {
            if let Some(c) = core.constraints.get_mut(id) {
                c.slack = Some(val);
            }
        }
    }

    fn set_variable_values_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = self.core.borrow_mut();
        for v in &mut core.vars {
            if let Some(&val) = values.get(&v.name) {
                v.value = Some(val);
            }
        }
    }

    fn set_variable_djs_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = self.core.borrow_mut();
        for v in &mut core.vars {
            if let Some(&val) = values.get(&v.name) {
                v.dj = Some(val);
            }
        }
    }

    fn set_constraint_pis_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = self.core.borrow_mut();
        for c in &mut core.constraints {
            if let Some(&val) = values.get(&c.name) {
                c.pi = Some(val);
            }
        }
    }

    fn set_constraint_slacks_by_name(&self, values: std::collections::HashMap<String, f64>) {
        let mut core = self.core.borrow_mut();
        for c in &mut core.constraints {
            if let Some(&val) = values.get(&c.name) {
                c.slack = Some(val);
            }
        }
    }

    fn constraints_dict(&self) -> Vec<(String, Constraint)> {
        let core = self.core.borrow();
        core.constraints
            .iter()
            .enumerate()
            .map(|(id, c)| {
                (
                    c.name.clone(),
                    Constraint {
                        id,
                        model: Rc::downgrade(&self.core),
                    },
                )
            })
            .collect()
    }

    fn variables_dict(&self) -> Vec<(String, Variable)> {
        let core = self.core.borrow();
        core.vars
            .iter()
            .enumerate()
            .map(|(id, v)| {
                (
                    v.name.clone(),
                    Variable {
                        id,
                        model: Rc::downgrade(&self.core),
                    },
                )
            })
            .collect()
    }

    fn get_constraint_by_name(&self, name: &str) -> Option<Constraint> {
        let core = self.core.borrow();
        core.constraints
            .iter()
            .enumerate()
            .find(|(_, c)| c.name == name)
            .map(|(id, _)| Constraint {
                id,
                model: Rc::downgrade(&self.core),
            })
    }

    // ── Phase 3 methods ──

    /// Whether any variable is Integer or Binary.
    fn is_mip(&self) -> bool {
        let core = self.core.borrow();
        core.vars
            .iter()
            .any(|v| v.category == Category::Integer || v.category == Category::Binary)
    }

    /// Round all variable values to bounds and integrality.
    #[pyo3(signature = (eps_int=1e-5, eps=1e-7))]
    fn round_solution(&self, eps_int: f64, eps: f64) {
        let mut core = self.core.borrow_mut();
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
        let core = self.core.borrow();
        let mut seen = std::collections::HashMap::new();
        for vd in &core.vars {
            *seen.entry(vd.name.clone()).or_insert(0usize) += 1;
        }
        let repeated: Vec<(String, usize)> =
            seen.into_iter().filter(|(_, c)| *c >= 2).collect();
        if !repeated.is_empty() {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
                "Repeated variable names: {:?}",
                repeated
                    .iter()
                    .map(|(n, c)| format!("('{}', {})", n, c))
                    .collect::<Vec<_>>()
                    .join(", ")
            )));
        }
        Ok(())
    }

    /// Check that no variable name exceeds max_length.
    fn check_length_vars(&self, max_length: usize) -> PyResult<()> {
        let core = self.core.borrow();
        let long: Vec<String> = core
            .vars
            .iter()
            .filter(|v| v.name.len() > max_length)
            .map(|v| v.name.clone())
            .collect();
        if !long.is_empty() {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
                "Variable names too long for Lp format: {:?}",
                long
            )));
        }
        Ok(())
    }

    /// Return all (variable_name, constraint_name, coefficient) triples.
    fn coefficients(&self) -> Vec<(String, String, f64)> {
        let core = self.core.borrow();
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

    /// Deep-copy the entire model (new Rc, new data).
    fn copy_model(&self) -> Self {
        let core = self.core.borrow();
        let new_core = ModelCore {
            name: core.name.clone(),
            vars: core.vars.clone(),
            constraints: core.constraints.clone(),
            objective: core.objective.clone(),
            sense: core.sense,
        };
        let next_id = self.next_constraint_id;
        Self {
            core: Rc::new(RefCell::new(new_core)),
            next_constraint_id: next_id,
        }
    }
}
