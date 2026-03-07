//! Python-exposed Model (high-level handle to ModelCore).

use std::cell::RefCell;
use std::rc::Rc;

use indexmap::IndexMap;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use crate::constraint::Constraint;
use crate::types::{Category, ConstrId, ModelCore, ObjSense, Sense, VarId};
use crate::variable::Variable;

/// High-level model handle exposed to Python.
#[pyclass(unsendable)]
pub struct Model {
    pub core: Rc<RefCell<ModelCore>>,
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

    fn add_constraint(
        &mut self,
        name: String,
        coeffs: Vec<(Variable, f64)>,
        rhs: f64,
        sense: Sense,
    ) -> Constraint {
        let mut map = IndexMap::new();
        for (var, coeff) in coeffs {
            let entry = map.entry(var.id()).or_insert(0.0);
            *entry += coeff;
        }
        let id = self
            .core
            .borrow_mut()
            .add_constraint(name, map, rhs, sense);
        Constraint {
            id,
            model: Rc::downgrade(&self.core),
        }
    }

    fn set_objective(
        &mut self,
        coeffs: Vec<(Variable, f64)>,
        constant: f64,
        sense: ObjSense,
    ) {
        let mut map = IndexMap::new();
        for (var, coeff) in coeffs {
            let entry = map.entry(var.id()).or_insert(0.0);
            *entry += coeff;
        }
        self.core
            .borrow_mut()
            .set_objective(map, constant, sense);
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

    fn get_constraint_data(
        &self,
        id: ConstrId,
    ) -> PyResult<(String, f64, Sense, Vec<(Variable, f64)>)> {
        let (name, rhs, sense, coeffs_map) = {
            let core = self.core.borrow();
            let c = core
                .constraints
                .get(id)
                .ok_or_else(|| PyRuntimeError::new_err("Constraint id out of range"))?;
            let coeffs_map = c.coeffs.clone();
            (
                c.name.clone(),
                c.rhs,
                c.sense,
                coeffs_map,
            )
        };
        let coeffs: Vec<(Variable, f64)> = coeffs_map
            .into_iter()
            .map(|(var_id, coeff)| {
                (
                    Variable {
                        id: var_id,
                        model: Rc::downgrade(&self.core),
                    },
                    coeff,
                )
            })
            .collect();
        Ok((name, rhs, sense, coeffs))
    }

    fn get_objective(
        &self,
    ) -> Option<(Vec<(Variable, f64)>, f64, ObjSense)> {
        let core = self.core.borrow();
        let obj = core.objective.as_ref()?;
        let coeffs: Vec<(Variable, f64)> = obj
            .coeffs
            .iter()
            .map(|(var_id, coeff)| {
                (
                    Variable {
                        id: *var_id,
                        model: Rc::downgrade(&self.core),
                    },
                    *coeff,
                )
            })
            .collect();
        Some((coeffs, obj.constant, obj.sense))
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
}
