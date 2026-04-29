//! Constraint handle (constraint stored in a ModelCore). Only created by Model.

use pyo3::prelude::*;

use crate::format;
use crate::types::{lock_model, upgrade_model, ConstrId, Sense, WeakModelCore};
use crate::variable::Variable;

/// Handle to a constraint stored inside a `ModelCore`. Only created by the model.
#[pyclass(from_py_object)]
#[derive(Clone)]
pub struct Constraint {
    pub id: ConstrId,
    pub model: WeakModelCore,
}

#[pymethods]
impl Constraint {
    fn id(&self) -> ConstrId {
        self.id
    }

    #[getter]
    fn name(&self) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        Ok(core
            .constraints
            .get(self.id)
            .map(|c| c.name.clone())
            .unwrap_or_default())
    }

    fn set_name(&self, name: String) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = lock_model(&core_rc);
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.name = name;
        }
        Ok(())
    }

    #[getter]
    fn pi(&self) -> PyResult<Option<f64>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        Ok(core.constraints[self.id].pi)
    }

    fn set_pi(&self, v: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = lock_model(&core_rc);
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.pi = Some(v);
        }
        Ok(())
    }

    #[getter]
    fn slack(&self) -> PyResult<Option<f64>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        Ok(core.constraints[self.id].slack)
    }

    fn set_slack(&self, v: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = lock_model(&core_rc);
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.slack = Some(v);
        }
        Ok(())
    }

    #[getter]
    fn sense(&self) -> PyResult<Sense> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        Ok(core.constraints[self.id].sense)
    }

    #[getter]
    fn rhs(&self) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        Ok(core.constraints[self.id].rhs)
    }

    fn items(&self) -> PyResult<Vec<(Variable, f64)>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let c = &core.constraints[self.id];
        Ok(c.coeffs
            .iter()
            .map(|(&var_id, &coeff)| {
                (
                    Variable {
                        id: var_id,
                        model: self.model.clone(),
                    },
                    coeff,
                )
            })
            .collect())
    }

    // ── Value / validation methods ──

    fn value(&self) -> PyResult<Option<f64>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let cd = &core.constraints[self.id];
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        let mut total = constant;
        for (&var_id, &coeff) in &cd.coeffs {
            match core.vars.get(var_id).and_then(|vd| vd.value) {
                Some(val) => total += val * coeff,
                None => return Ok(None),
            }
        }
        Ok(Some(total))
    }

    fn value_or_default(&self) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let cd = &core.constraints[self.id];
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        let mut total = constant;
        for (&var_id, &coeff) in &cd.coeffs {
            if let Some(vd) = core.vars.get(var_id) {
                let v = vd.value.unwrap_or_else(|| format::default_value(vd.lb, vd.ub));
                total += v * coeff;
            }
        }
        Ok(total)
    }

    #[pyo3(signature = (eps=0.0))]
    fn valid(&self, eps: f64) -> PyResult<bool> {
        let val = match self.value()? {
            Some(v) => v,
            None => return Ok(false),
        };
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let cd = &core.constraints[self.id];
        Ok(match cd.sense {
            Sense::Equal => val.abs() <= eps,
            Sense::LessEqual => val * (-1.0) >= -eps,
            Sense::GreaterEqual => val >= -eps,
        })
    }

    // ── Formatting methods (delegate to format.rs) ──

    fn as_cplex_lp_constraint(&self, name: &str) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
        Ok(format::cplex_lp_constraint(
            &sorted,
            cd.sense,
            rhs,
            name,
            cd.coeffs.is_empty(),
        ))
    }

    #[pyo3(signature = (name, include_constant=true))]
    fn as_cplex_lp_affine_expression(&self, name: &str, include_constant: bool) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        Ok(format::cplex_lp_affine_expression(
            &sorted,
            constant,
            name,
            include_constant,
        ))
    }

    fn str_repr(&self) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        Ok(format::str_constraint(&sorted, cd.sense, -cd.rhs))
    }

    fn repr_str(&self) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = lock_model(&core_rc);
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        Ok(format::repr_expr(&sorted, constant, Some(cd.sense)))
    }
}
