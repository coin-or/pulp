//! Variable handle (variable stored in a ModelCore). Only created by Model.
//! Model is always present; no optional fallbacks.

use pyo3::prelude::*;
use std::cell::RefCell;
use std::rc::Weak;
use crate::types::{upgrade_model, VarId, ModelCore};

/// Handle to a variable stored inside a `ModelCore`. Only created by the model.
#[pyclass(unsendable)]
#[derive(Clone)]
pub struct Variable {
    pub id: VarId,
    pub model: Weak<RefCell<ModelCore>>,
}

#[pymethods]
impl Variable {
    pub fn id(&self) -> VarId {
        self.id
    }

    #[getter]
    fn name(&self) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars
            .get(self.id)
            .map(|v| v.name.clone())
            .unwrap_or_default()
    }

    #[getter]
    fn lb(&self) -> f64 {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].lb
    }

    #[getter]
    fn ub(&self) -> f64 {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].ub
    }

    #[getter]
    fn category(&self) -> crate::types::Category {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].category
    }

    #[getter]
    fn value(&self) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].value
    }

    fn set_value(&self, v: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.value = Some(v);
        }
    }

    fn set_lb(&self, lb: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.lb = lb;
        }
    }

    fn set_ub(&self, ub: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.ub = ub;
        }
    }

    fn set_name(&self, name: String) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.name = name;
        }
    }

    #[getter]
    fn dj(&self) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].dj
    }

    fn set_dj(&self, v: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.dj = Some(v);
        }
    }
}
