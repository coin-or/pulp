//! Python-exposed Model (high-level handle to ModelCore).

use std::cell::RefCell;
use std::rc::Rc;

use pyo3::prelude::*;

use crate::affine_expr::AffineExpr;
use crate::constraint::Constraint;
use crate::types::{get_model_optional, Category, ConstrId, ModelCore, ObjSense, VarId};
use crate::variable::Variable;

/// High-level model handle exposed to Python.
#[pyclass(unsendable)]
pub struct Model {
    pub core: Rc<RefCell<ModelCore>>,
}

impl Model {
    /// Wrap an existing core (same `Rc` as variables). Used by `Variable::containing_model`.
    pub(crate) fn from_shared_core(core: Rc<RefCell<ModelCore>>) -> Self {
        Self { core }
    }
}

#[pymethods]
impl Model {
    #[new]
    fn new(name: Option<String>) -> Self {
        let name = name.unwrap_or_else(|| "Model".to_string());
        let core = Rc::new(RefCell::new(ModelCore::new(name)));
        Self { core }
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

    fn add_constraint(&mut self, expr: &AffineExpr) -> PyResult<Constraint> {
        let mut e = expr.clone();
        if e.model.is_none() {
            e.model = Some(Rc::downgrade(&self.core));
        } else {
            let expr_core = get_model_optional(&e.model)?;
            if !Rc::ptr_eq(&expr_core, &self.core) {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Expression is bound to a different model than the one receiving the constraint.",
                ));
            }
        }
        let id = self.core.borrow_mut().add_constraint(&e)?;
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
        let mut core = self.core.borrow_mut();
        for name in names {
            core.add_variable(name, lb, ub, category);
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
        self.core.borrow().check_duplicate_var_names()
    }

    /// Check for duplicate constraint names.
    fn check_duplicate_constraints(&self) -> PyResult<()> {
        self.core.borrow().check_duplicate_constraint_names()
    }

    /// Check that no variable name exceeds max_length.
    fn check_length_vars(&self, max_length: usize) -> PyResult<()> {
        self.core.borrow().check_var_name_lengths(max_length)
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
            next_auto_constraint_id: core.next_auto_constraint_id,
        };
        let new_rc = Rc::new(RefCell::new(new_core));
        {
            let mut inner = new_rc.borrow_mut();
            if let Some(ref mut obj) = inner.objective {
                obj.model = Some(Rc::downgrade(&new_rc));
            }
        }
        Self { core: new_rc }
    }
}
