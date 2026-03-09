//! Constraint handle (constraint stored in a ModelCore). Only created by Model.
//! Model is always present; no optional fallbacks.

use pyo3::prelude::*;

use crate::types::{upgrade_model, ConstrId};

/// Handle to a constraint stored inside a `ModelCore`. Only created by the model.
#[pyclass(unsendable)]
#[derive(Clone)]
pub struct Constraint {
    pub id: ConstrId,
    pub model: std::rc::Weak<std::cell::RefCell<crate::types::ModelCore>>,
}

#[pymethods]
impl Constraint {
    fn id(&self) -> ConstrId {
        self.id
    }

    #[getter]
    fn name(&self) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints
            .get(self.id)
            .map(|c| c.name.clone())
            .unwrap_or_default()
    }

    #[getter]
    fn pi(&self) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].pi
    }

    fn set_pi(&self, v: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.pi = Some(v);
        }
    }

    #[getter]
    fn slack(&self) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].slack
    }

    fn set_slack(&self, v: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.slack = Some(v);
        }
    }

    #[getter]
    fn sense(&self) -> crate::types::Sense {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].sense
    }

    #[getter]
    fn rhs(&self) -> f64 {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].rhs
    }

    fn items(&self) -> Vec<(crate::variable::Variable, f64)> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let c = &core.constraints[self.id];
        c.coeffs
            .iter()
            .map(|(&var_id, &coeff)| {
                (
                    crate::variable::Variable {
                        id: var_id,
                        model: self.model.clone(),
                    },
                    coeff,
                )
            })
            .collect()
    }
}
