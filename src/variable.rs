//! Variable handle (variable stored in a ModelCore). Only created by Model.
//! Model is always present; no optional fallbacks.

use pyo3::prelude::*;
use std::cell::RefCell;
use std::rc::Weak;

use crate::format;
use crate::types::{upgrade_model, Category, ModelCore, VarId};

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
    fn category(&self) -> Category {
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

    // ── Property checks ──

    fn is_binary(&self) -> bool {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].is_binary()
    }

    fn is_integer(&self) -> bool {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].is_integer()
    }

    fn is_free(&self) -> bool {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].is_free()
    }

    fn is_constant(&self) -> bool {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].is_constant()
    }

    fn is_positive(&self) -> bool {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.vars[self.id].is_positive()
    }

    /// CPLEX LP bounds string for this variable.
    fn as_cplex_lp_variable(&self) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        format::cplex_lp_variable(&core.vars[self.id])
    }

    /// Validate the variable value against its bounds and integrality.
    #[pyo3(signature = (eps=1e-7))]
    fn valid(&self, eps: f64) -> bool {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        if vd.name == "__dummy" && vd.value.is_none() {
            return true;
        }
        let val = match vd.value {
            Some(v) => v,
            None => return false,
        };
        if vd.ub.is_finite() && val > vd.ub + eps {
            return false;
        }
        if vd.lb.is_finite() && val < vd.lb - eps {
            return false;
        }
        if vd.category == Category::Integer && (val.round() - val).abs() > eps {
            return false;
        }
        true
    }

    /// Infeasibility gap (distance from feasible region).
    #[pyo3(signature = (mip=true))]
    fn infeasibility_gap(&self, mip: bool) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        let val = vd
            .value
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("variable value is None"))?;
        if vd.ub.is_finite() && val > vd.ub {
            return Ok(val - vd.ub);
        }
        if vd.lb.is_finite() && val < vd.lb {
            return Ok(val - vd.lb);
        }
        if mip && vd.category == Category::Integer && (val.round() - val) != 0.0 {
            return Ok(val.round() - val);
        }
        Ok(0.0)
    }

    /// Round variable value to bounds and integer if appropriate.
    #[pyo3(signature = (eps_int=1e-5, eps=1e-7))]
    fn round_value(&self, eps_int: f64, eps: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        let vd = &mut core.vars[self.id];
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

    /// Value or default from bounds (used when no solution exists).
    fn value_or_default(&self) -> f64 {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        if let Some(v) = vd.value {
            return v;
        }
        let lb = vd.lb;
        let ub = vd.ub;
        let lb_fin = lb.is_finite();
        let ub_fin = ub.is_finite();
        if lb_fin && ub_fin {
            if 0.0 >= lb && 0.0 <= ub {
                0.0
            } else if lb >= 0.0 {
                lb
            } else {
                ub
            }
        } else if lb_fin {
            if 0.0 >= lb { 0.0 } else { lb }
        } else if ub_fin {
            if 0.0 <= ub { 0.0 } else { ub }
        } else {
            0.0
        }
    }

    /// Rounded value for integer variables.
    #[pyo3(signature = (eps=1e-5))]
    fn rounded_value(&self, eps: f64) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        match vd.value {
            Some(v) if vd.category == Category::Integer && (v - v.round()).abs() <= eps => {
                Some(v.round())
            }
            other => other,
        }
    }
}
