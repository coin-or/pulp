//! Python-exposed Constraint handle (constraint stored in a ModelCore).

use pyo3::prelude::*;

use crate::types::{upgrade_model, ConstrId};

/// Handle to a constraint stored inside a `ModelCore`.
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
    fn name(&self) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core
            .constraints
            .get(self.id)
            .map(|c| c.name.clone())
            .unwrap_or_default())
    }
}
