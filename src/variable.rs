//! Python-exposed Variable handle (variable stored in a ModelCore).

use pyo3::prelude::*;

use crate::types::{upgrade_model, VarId};

/// Handle to a variable stored inside a `ModelCore`.
#[pyclass(unsendable)]
#[derive(Clone)]
pub struct Variable {
    pub id: VarId,
    pub model: std::rc::Weak<std::cell::RefCell<crate::types::ModelCore>>,
}

#[pymethods]
impl Variable {
    pub fn id(&self) -> VarId {
        self.id
    }

    #[getter]
    fn name(&self) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core
            .vars
            .get(self.id)
            .map(|v| v.name.clone())
            .unwrap_or_default())
    }

    #[getter]
    fn lb(&self) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].lb)
    }

    #[getter]
    fn ub(&self) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].ub)
    }

    #[getter]
    fn category(&self) -> PyResult<crate::types::Category> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].category)
    }

    #[getter]
    fn value(&self) -> PyResult<Option<f64>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].value)
    }

    fn set_value(&self, v: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.value = Some(v);
        }
        Ok(())
    }

    fn set_lb(&self, lb: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.lb = lb;
        }
        Ok(())
    }

    fn set_ub(&self, ub: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.ub = ub;
        }
        Ok(())
    }

    fn set_name(&self, name: String) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.name = name;
        }
        Ok(())
    }
}
